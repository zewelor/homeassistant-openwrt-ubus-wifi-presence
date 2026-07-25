from __future__ import annotations

from unittest.mock import AsyncMock

from aiohttp import ClientError
import pytest

from custom_components.openwrt_ubus.api import (
    OpenWrtUbusAuthenticationError,
    OpenWrtUbusClient,
    OpenWrtUbusCommunicationError,
)
from custom_components.openwrt_ubus.api.client import OpenWrtUbusRpcCallError


def _client() -> OpenWrtUbusClient:
    return OpenWrtUbusClient(
        session=AsyncMock(),
        url="http://192.168.1.1/ubus",
        host="192.168.1.1",
        username="root",
        password="secretpassword",
        verify_ssl=False,
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


@pytest.mark.unit
async def test_wifi_ssid_inventory_includes_interface_without_ifname() -> None:
    """Test that configured WiFi SSIDs include temporarily inactive interfaces."""
    client = _client()
    client.call = AsyncMock(
        return_value={
            "radio0": {
                "interfaces": [
                    {"ifname": "wlan0", "config": {"ssid": "Home WiFi"}},
                    {"config": {"ssid": "Guest WiFi"}},
                ]
            }
        }
    )

    mapping, configured_ssids, complete = await client.get_wifi_ssid_inventory()

    assert mapping == {"wlan0": "Home WiFi"}
    assert configured_ssids == {"Home WiFi", "Guest WiFi"}
    assert complete is True


@pytest.mark.unit
@pytest.mark.parametrize(
    "second_radio_result",
    [
        {},
        OpenWrtUbusRpcCallError(code=4, subsystem="network.wireless", rpc_method="status"),
    ],
)
async def test_wifi_ssid_inventory_marks_partial_device_fallback_incomplete(
    second_radio_result: dict[str, object] | OpenWrtUbusRpcCallError,
) -> None:
    """Test that partial radio status cannot authorize destructive cleanup."""
    client = _client()
    client._wireless_status_requires_device = True  # noqa: SLF001
    client.call = AsyncMock(
        side_effect=[
            {
                "values": {
                    "radio0": {".type": "wifi-device", ".name": "radio0"},
                    "radio1": {".type": "wifi-device", ".name": "radio1"},
                }
            },
            {"radio0": {"interfaces": [{"ifname": "wlan0", "config": {"ssid": "Home WiFi"}}]}},
            second_radio_result,
        ]
    )

    mapping, configured_ssids, complete = await client.get_wifi_ssid_inventory()

    assert mapping == {"wlan0": "Home WiFi"}
    assert configured_ssids == {"Home WiFi"}
    assert complete is False


@pytest.mark.unit
async def test_wifi_ssid_inventory_marks_failed_uci_fallback_incomplete() -> None:
    """Test that a failed UCI fallback returns no authoritative inventory."""
    client = _client()
    client._wireless_status_requires_device = True  # noqa: SLF001
    client.call = AsyncMock(side_effect=OpenWrtUbusCommunicationError("permission denied"))

    mapping, configured_ssids, complete = await client.get_wifi_ssid_inventory()

    assert mapping == {}
    assert configured_ssids == set()
    assert complete is False


@pytest.mark.unit
async def test_wifi_ssid_inventory_marks_malformed_uci_fallback_incomplete() -> None:
    """Test that malformed UCI sections cannot authorize destructive cleanup."""
    client = _client()
    client._wireless_status_requires_device = True  # noqa: SLF001
    client.call = AsyncMock(return_value={"values": {"radio0": None}})

    mapping, configured_ssids, complete = await client.get_wifi_ssid_inventory()

    assert mapping == {}
    assert configured_ssids == set()
    assert complete is False
