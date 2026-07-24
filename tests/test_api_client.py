from __future__ import annotations

from unittest.mock import AsyncMock

from aiohttp import ClientError
import pytest

from custom_components.openwrt_ubus.api import (
    OpenWrtUbusAuthenticationError,
    OpenWrtUbusClient,
    OpenWrtUbusCommunicationError,
)


@pytest.mark.unit
async def test_client_call_session_retry_success() -> None:
    """Test that a call returning code 6 triggers auto-reconnect and succeeds on retry."""
    mock_session = AsyncMock()

    # Response 1: Old session call returns ubus code 6 (Permission Denied / Expired session after reboot)
    res_old_session = AsyncMock()
    res_old_session.status = 200
    res_old_session.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": [6]}

    # Response 2: Re-connect session.login call returns new valid session ID
    res_login = AsyncMock()
    res_login.status = 200
    res_login.json.return_value = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": [0, {"ubus_rpc_session": "new_session_12345678", "expires": 300}],
    }

    # Response 3: Retried call with new session ID returns valid result
    res_retry_call = AsyncMock()
    res_retry_call.status = 200
    res_retry_call.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": [0, {"devices": ["wlan0"]}]}

    mock_session.post.side_effect = [res_old_session, res_login, res_retry_call]

    client = OpenWrtUbusClient(
        session=mock_session,
        url="http://192.168.1.1/ubus",
        host="192.168.1.1",
        username="root",
        password="secretpassword",
        verify_ssl=False,
    )
    # Simulate active session before router reboot
    client._session_id = "old_session_87654321"  # noqa: SLF001

    result = await client.call("iwinfo", "devices", {})

    assert result == {"devices": ["wlan0"]}
    assert client._session_id == "new_session_12345678"  # noqa: SLF001
    assert mock_session.post.call_count == 3


@pytest.mark.unit
async def test_client_call_session_retry_fails_when_credentials_invalid() -> None:
    """Test that when auto-reconnect login fails with invalid credentials, OpenWrtUbusAuthenticationError is raised."""
    mock_session = AsyncMock()

    # Response 1: Old session call returns code 6
    res_old_session = AsyncMock()
    res_old_session.status = 200
    res_old_session.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": [6]}

    # Response 2: Re-connect login also returns code 6 (bad credentials)
    res_login = AsyncMock()
    res_login.status = 200
    res_login.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": [6]}

    mock_session.post.side_effect = [res_old_session, res_login]

    client = OpenWrtUbusClient(
        session=mock_session,
        url="http://192.168.1.1/ubus",
        host="192.168.1.1",
        username="root",
        password="wrongpassword",
        verify_ssl=False,
    )
    client._session_id = "old_session_87654321"  # noqa: SLF001

    with pytest.raises(OpenWrtUbusAuthenticationError):
        await client.call("iwinfo", "devices", {})


@pytest.mark.unit
async def test_client_call_session_retry_fails_on_communication_error() -> None:
    """Test that when router is booting/unreachable during reconnect, OpenWrtUbusCommunicationError is raised."""
    mock_session = AsyncMock()

    # Response 1: Old session call returns code 6
    res_old_session = AsyncMock()
    res_old_session.status = 200
    res_old_session.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": [6]}

    # Response 2: Re-connect login fails due to connection error (router rebooting)
    mock_session.post.side_effect = [res_old_session, ClientError("Connection refused")]

    client = OpenWrtUbusClient(
        session=mock_session,
        url="http://192.168.1.1/ubus",
        host="192.168.1.1",
        username="root",
        password="secretpassword",
        verify_ssl=False,
    )
    client._session_id = "old_session_87654321"  # noqa: SLF001

    with pytest.raises(OpenWrtUbusCommunicationError):
        await client.call("iwinfo", "devices", {})
