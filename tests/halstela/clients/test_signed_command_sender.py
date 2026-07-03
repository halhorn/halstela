"""halstela.clients.signed_command_sender のテスト"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from halstela.clients.signed_command_sender import SignedCommandSender

# テスト用 EC 秘密鍵（SECP256R1）
_TEST_PRIVATE_KEY_PEM = """\
-----BEGIN EC PRIVATE KEY-----
MHcCAQEEILieGz8R54+IGjnCfuinREhVr/zwS4CbHbhZWRK2/+0LoAoGCCqGSM49
AwEHoUQDQgAE8qx9ea3xCRnfwl50JVOcOBaK6H+Zr2HWmGNNVoVzPQKcsF6lTHyE
H9FhUR0dZNTy2GPMvSddeEsEavUsEoknqA==
-----END EC PRIVATE KEY-----"""


@pytest.fixture
def sender() -> SignedCommandSender:
    return SignedCommandSender(
        access_token="test-token",
        private_key_pem=_TEST_PRIVATE_KEY_PEM,
        base_url="https://example.com",
    )


class TestSignedCommandSender:
    def test_unsupported_command_raises(self, sender: SignedCommandSender) -> None:
        with pytest.raises(NotImplementedError, match="not supported"):
            sender.send_command("VIN1", "unsupported_command")

    @patch("halstela.clients.signed_command_sender.TeslaFleetApi")
    @patch("halstela.clients.signed_command_sender.aiohttp.ClientSession")
    def test_auto_conditioning_start(
        self,
        mock_session_cls: MagicMock,
        mock_api_cls: MagicMock,
        sender: SignedCommandSender,
    ) -> None:
        mock_vehicle = MagicMock()
        mock_vehicle.auto_conditioning_start = AsyncMock(
            return_value={"response": {"result": True, "reason": ""}}
        )

        mock_api = MagicMock()
        mock_api.vehicles.createSigned.return_value = mock_vehicle
        mock_api_cls.return_value = mock_api

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_session

        result = sender.send_command("VIN1", "auto_conditioning_start")

        assert result == {"result": True, "reason": ""}
        mock_api.vehicles.createSigned.assert_called_once_with("VIN1")
        mock_vehicle.auto_conditioning_start.assert_awaited_once()

    @patch("halstela.clients.signed_command_sender.TeslaFleetApi")
    @patch("halstela.clients.signed_command_sender.aiohttp.ClientSession")
    def test_auto_conditioning_stop(
        self,
        mock_session_cls: MagicMock,
        mock_api_cls: MagicMock,
        sender: SignedCommandSender,
    ) -> None:
        mock_vehicle = MagicMock()
        mock_vehicle.auto_conditioning_stop = AsyncMock(
            return_value={"response": {"result": True, "reason": ""}}
        )

        mock_api = MagicMock()
        mock_api.vehicles.createSigned.return_value = mock_vehicle
        mock_api_cls.return_value = mock_api

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_session

        result = sender.send_command("VIN1", "auto_conditioning_stop")

        assert result == {"result": True, "reason": ""}


class TestLoadPrivateKey:
    def test_invalid_key_type_raises(self) -> None:
        rsa_pem = """\
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEAswXCOxrISwYMeBKRkP2Gsw/HkwtfxkqlekFyw06VQzHrQUdq
pmXsduXpcXj2m0XmOvb9r5V212DClDpAEGZZm0ZU8B+bC3q/yllWWW6C9XtgNpRk
LRD7+OWUd/erikTvpoV0tB06o89IS40Tsb788Ks0Zy5gB68UAc0Bwb1h33Xt1Ifw
AweIVQZDQEu1AmF1lBMtIyIw8L/GoXSusPztVtcG2iRVMaWqywFyyZ8rS8x41ceb
T6cVRx7S5eIUPl2MuaiQr28wzjd7tRhYCRPesOVv+XTf8W5sbuKH99TabN0lLBCv
zMjYS/9c1569nSdE7mprwZ1hs6AGIxYnHoPlfwIDAQABAoIBACqwmNyXSmP5kUeg
xe2ZR2GzxZefAru6WTOKH9/LAXUAlmT+rsP3UigYM07H1aa5SGmPNHeGYMyDWmMW
cOh4P63zW5XXM5XNM6cBHsI8xCXdwdfCExFcF3oG5RymhtV2Et/WuzmoLq+ZYlgB
0Ex2isKpUNm6CVRLv62eQWj9zDUI99UduzZEwAZiCtJR0LX/PKgS18ZKLsUsN/OO
2ysjREUCY+dCod1FRJ9cG1rNu1zJEuIXZ14Nye5JD4kcHYznFBYE6TgS9qjGAEAw
7aNtXl28Vo4FXTDz1kvhOsDeMoxakd+XZWApFxoyQmHasHPPcure4sxZ7+MdaX4A
/YqDW+ECgYEA5PTM6I3BTV58o0TshVEOaHwLHjZG2iqu9whg66se7MsY4rh7MXaw
pLMXEEEfp3Ee7CHo6PJU28DTk2KRtN6qFk9u0/GnkGjGeuNAR86PjDsA6+uvtjwF
nNDm6LztU8rTMjFdJidZ2oqnmwuSiusw8bRL649k6ijCgT1w7WW+PQMCgYEAyCsO
kO0eBuLYwerIseQKV5r0ma9t5cGga3tZXlimHtArz/jt2u90oeXX/m5m6IXAn1Mv
dpVTJGzBnnyBVyquqcRvWRBm3oRKyUkTynC4lJacLFhFiUT0UppjClOXVbXwjhp1
mipXFlaVNWDmOOECd8BIFK9K8M8eku26ykZJttUCgYEA5JUa9pqAANRyrzaixL8W
GW6uUu1xc2Ll57Avw1nGuDZUlBYGuG19EhHS1uGNzsf7TVjVhaxa2EL9eMoSGner
bDbFuUgsONrCPfIgPRCW9DP8SY22kcP+/n756iak8uEuVZA/JVZoOO3xQ7QcDCGf
bdDJc1ZoM/eZqRpEYl8PvS0CgYAW5RXdbcGpd/ji9T/PWQ31xzuC+JXRWbxHjuxB
5lHZ5GWefBJ4oDru6aMy7t3GasYFczZSkfHYkLf0sLj6h19C+7zgqweZG/iR3VHu
LcZu+GsUh2Qstz5a1F3PqI/+tbi2CEC7SWx8mZqnaFXs24+0ssGL3CDuOkJ8+8QJ
rtBvoQKBgE8WtyJoX2jvuqJ2/+obhykLNCqmte1+Y22ih55SYQe1kxQ8GT5IXmvi
XkLGAEh9ls9RrJX2h0xaOOo0sauHKKmao23QXorQ5FJd30RztwVqyqc92xENRk93
dB5BdpokW70hja6h3T2s09Zcf7fMpes2Wyy4yq4FcdGpaX/7ya4S
-----END RSA PRIVATE KEY-----"""
        with pytest.raises(ValueError, match="EC key"):
            SignedCommandSender(
                access_token="test-token",
                private_key_pem=rsa_pem,
                base_url="https://example.com",
            )
