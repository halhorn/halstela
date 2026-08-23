"""Alexa Smart Home Skill Lambda ハンドラー"""

import logging
import os
import uuid
from typing import Any

from halstela.alexa.event_gateway import EventGatewayClient
from halstela.alexa.properties import report_state_properties
from halstela.clients.tesla_fleet_client import TeslaFleetClient
from halstela.clients.worker_invoker import WorkerInvoker
from halstela.config import TeslaConfig
from halstela.models.vehicle import Vehicle
from halstela.models.worker_command import WorkerCommand
from halstela.services.vehicle_service import VehicleService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    directive = event.get("directive", {})
    header = directive.get("header", {})
    namespace = header.get("namespace", "")
    name = header.get("name", "")

    logger.info(f"Directive: {namespace}.{name}")

    try:
        if namespace == "Alexa.Discovery" and name == "Discover":
            return handle_discovery(directive)
        if namespace == "Alexa.Authorization" and name == "AcceptGrant":
            return handle_accept_grant(directive)
        if namespace == "Alexa.PowerController":
            return handle_power_control(directive)
        if namespace == "Alexa" and name == "ReportState":
            return handle_report_state(directive)

        return _error_response(directive, "INVALID_DIRECTIVE", f"Unsupported: {namespace}.{name}")
    except Exception:
        logger.exception(f"Error handling {namespace}.{name}")
        return _error_response(directive, "INTERNAL_ERROR", "Internal error")


# ── Discovery ──


def handle_discovery(directive: dict[str, Any]) -> dict[str, Any]:
    token = directive["payload"]["scope"]["token"]
    config = TeslaConfig.from_env()

    with TeslaFleetClient(token, config.fleet_api_base_url) as client:
        service = VehicleService(client)
        vehicles = service.get_vehicles()

    return {
        "event": {
            "header": {
                "namespace": "Alexa.Discovery",
                "name": "Discover.Response",
                "payloadVersion": "3",
                "messageId": _message_id(),
            },
            "payload": {
                "endpoints": [_build_endpoint(v) for v in vehicles],
            },
        },
    }


# ── PowerController ──


def handle_power_control(directive: dict[str, Any]) -> dict[str, Any]:
    header = directive["header"]
    name = header["name"]
    endpoint = directive["endpoint"]
    token = endpoint["scope"]["token"]
    vehicle_id = endpoint["endpointId"]

    if name != "TurnOn":
        return _error_response(
            directive, "INVALID_DIRECTIVE", f"Unsupported: PowerController.{name}"
        )

    command = WorkerCommand(
        access_token=token,
        vehicle_id=vehicle_id,
        command="auto_conditioning_start",
        correlation_token=header.get("correlationToken") or None,
    )
    _create_worker_invoker().invoke_async(command)

    return {
        "event": {
            "header": {
                "namespace": "Alexa",
                "name": "Response",
                "payloadVersion": "3",
                "messageId": _message_id(),
                "correlationToken": header.get("correlationToken", ""),
            },
            "endpoint": {"endpointId": vehicle_id},
            "payload": {},
        },
    }


def _create_worker_invoker() -> WorkerInvoker:
    return WorkerInvoker(os.environ["COMMAND_WORKER_ARN"])


# ── Authorization（Event Gateway 用 LWA トークン）──


def handle_accept_grant(directive: dict[str, Any]) -> dict[str, Any]:
    code = directive["payload"]["grant"]["code"]
    try:
        with _create_event_gateway_client() as gateway:
            gateway.accept_grant(code=code)
    except Exception as exc:
        logger.exception(f"AcceptGrant failed: {exc!r}")
        return {
            "event": {
                "header": {
                    "namespace": "Alexa.Authorization",
                    "name": "ErrorResponse",
                    "payloadVersion": "3",
                    "messageId": _message_id(),
                },
                "payload": {
                    "type": "ACCEPT_GRANT_FAILED",
                    "message": "Failed to handle the AcceptGrant directive",
                },
            }
        }

    return {
        "event": {
            "header": {
                "namespace": "Alexa.Authorization",
                "name": "AcceptGrant.Response",
                "payloadVersion": "3",
                "messageId": _message_id(),
            },
            "payload": {},
        }
    }


def _create_event_gateway_client() -> EventGatewayClient:
    return EventGatewayClient.from_env()


# ── ReportState ──


def handle_report_state(directive: dict[str, Any]) -> dict[str, Any]:
    header = directive["header"]
    endpoint = directive["endpoint"]
    token = endpoint["scope"]["token"]
    vehicle_id = endpoint["endpointId"]
    config = TeslaConfig.from_env()

    with TeslaFleetClient(token, config.fleet_api_base_url) as client:
        service = VehicleService(client)
        climate = service.get_climate_state(vehicle_id)

    return {
        "event": {
            "header": {
                "namespace": "Alexa",
                "name": "StateReport",
                "payloadVersion": "3",
                "messageId": _message_id(),
                "correlationToken": header.get("correlationToken", ""),
            },
            "endpoint": {"endpointId": vehicle_id},
            "payload": {},
        },
        "context": {
            "properties": [
                prop.to_serializable() for prop in report_state_properties(climate=climate)
            ],
        },
    }


# ── Error ──


def _error_response(directive: dict[str, Any], error_type: str, message: str) -> dict[str, Any]:
    header = directive.get("header", {})
    endpoint = directive.get("endpoint", {})

    resp: dict[str, Any] = {
        "event": {
            "header": {
                "namespace": "Alexa",
                "name": "ErrorResponse",
                "payloadVersion": "3",
                "messageId": _message_id(),
                "correlationToken": header.get("correlationToken", ""),
            },
            "payload": {
                "type": error_type,
                "message": message,
            },
        },
    }
    if endpoint:
        resp["event"]["endpoint"] = {
            "endpointId": endpoint.get("endpointId", ""),
        }
    return resp


# ── Helpers ──


def _build_endpoint(vehicle: Vehicle) -> dict[str, Any]:
    return {
        "endpointId": vehicle.vin,
        "manufacturerName": "Tesla",
        "friendlyName": vehicle.display_name or "Tesla",
        "description": f"Tesla {vehicle.display_name}",
        "displayCategories": ["AIR_CONDITIONER"],
        "capabilities": [
            {
                "type": "AlexaInterface",
                "interface": "Alexa.PowerController",
                "version": "3",
                "properties": {
                    "supported": [{"name": "powerState"}],
                    "proactivelyReported": True,
                    "retrievable": True,
                },
            },
            {
                "type": "AlexaInterface",
                "interface": "Alexa.TemperatureSensor",
                "version": "3",
                "properties": {
                    "supported": [{"name": "temperature"}],
                    "proactivelyReported": True,
                    "retrievable": True,
                },
            },
            {
                "type": "AlexaInterface",
                "interface": "Alexa.EndpointHealth",
                "version": "3.2",
                "properties": {
                    "supported": [{"name": "connectivity"}],
                    "proactivelyReported": True,
                    "retrievable": True,
                },
            },
            {
                "type": "AlexaInterface",
                "interface": "Alexa",
                "version": "3",
            },
        ],
    }


def _message_id() -> str:
    return str(uuid.uuid4())
