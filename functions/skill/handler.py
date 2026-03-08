"""Alexa Smart Home Skill Lambda ハンドラー"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from halstela.clients.tesla_fleet_client import TeslaFleetClient
from halstela.config import TeslaConfig
from halstela.models.climate_state import ClimateState
from halstela.models.vehicle import Vehicle
from halstela.services.vehicle_service import VehicleService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    directive = event.get("directive", {})
    header = directive.get("header", {})
    namespace = header.get("namespace", "")
    name = header.get("name", "")

    logger.info("Directive: %s.%s", namespace, name)

    try:
        if namespace == "Alexa.Discovery" and name == "Discover":
            return handle_discovery(directive)
        if namespace == "Alexa.PowerController":
            return handle_power_control(directive)
        if namespace == "Alexa" and name == "ReportState":
            return handle_report_state(directive)

        return _error_response(directive, "INVALID_DIRECTIVE", f"Unsupported: {namespace}.{name}")
    except Exception:
        logger.exception("Error handling %s.%s", namespace, name)
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
    config = TeslaConfig.from_env()

    with TeslaFleetClient(token, config.fleet_api_base_url) as client:
        service = VehicleService(client)
        if name == "TurnOn":
            result = service.start_air_conditioning(vehicle_id)
        else:
            return _error_response(
                directive, "INVALID_DIRECTIVE", f"Unsupported: PowerController.{name}"
            )

    if not result.success:
        return _error_response(directive, "ENDPOINT_UNREACHABLE", result.reason)

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
            "properties": _build_temperature_properties(climate),
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
                    "proactivelyReported": False,
                    "retrievable": False,
                },
            },
            {
                "type": "AlexaInterface",
                "interface": "Alexa.TemperatureSensor",
                "version": "3",
                "properties": {
                    "supported": [{"name": "temperature"}],
                    "proactivelyReported": False,
                    "retrievable": True,
                },
            },
            {
                "type": "AlexaInterface",
                "interface": "Alexa.EndpointHealth",
                "version": "3.2",
                "properties": {
                    "supported": [{"name": "connectivity"}],
                    "proactivelyReported": False,
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


def _build_temperature_properties(climate: ClimateState) -> list[dict[str, Any]]:
    now = _iso_now()
    properties: list[dict[str, Any]] = []

    if climate.inside_temp is not None:
        properties.append(
            {
                "namespace": "Alexa.TemperatureSensor",
                "name": "temperature",
                "value": {"value": climate.inside_temp, "scale": "CELSIUS"},
                "timeOfSample": now,
                "uncertaintyInMilliseconds": 60000,
            }
        )

    properties.append(
        {
            "namespace": "Alexa.EndpointHealth",
            "name": "connectivity",
            "value": {"value": "OK"},
            "timeOfSample": now,
            "uncertaintyInMilliseconds": 0,
        }
    )

    return properties


def _message_id() -> str:
    return str(uuid.uuid4())


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()
