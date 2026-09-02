from __future__ import annotations

import math
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openwrt_ubus.api import (
    OpenWrtUbusAuthenticationError,
    OpenWrtUbusClient,
    OpenWrtUbusClientError,
    OpenWrtUbusCommunicationError,
)
from custom_components.openwrt_ubus.const import (
    CONF_ENDPOINT,
    CONF_IP_ADDRESS,
    CONF_SCAN_INTERVAL,
    CONF_TRACKING_MODE,
    CONF_USE_HTTPS,
    DOMAIN,
)
from custom_components.openwrt_ubus.coordinator import OpenWrtUbusWifiPresenceCoordinator
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed


@pytest.mark.unit
async def test_coordinator_raises_config_entry_auth_failed_on_auth_error(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="ap-livingroom.example.com",
        data={
            CONF_HOST: "ap-livingroom.example.com",
            CONF_IP_ADDRESS: "",
            CONF_USE_HTTPS: False,
            CONF_PORT: None,
            CONF_VERIFY_SSL: False,
            CONF_ENDPOINT: "ubus",
            CONF_USERNAME: "root",
            CONF_PASSWORD: "secret",
        },
        options={CONF_TRACKING_MODE: "known_or_alias", CONF_SCAN_INTERVAL: 30},
    )

    client = AsyncMock()
    client.normalize_mac = OpenWrtUbusClient.normalize_mac
    client.get_wifi_ssid_inventory.side_effect = OpenWrtUbusAuthenticationError("invalid credentials")

    coordinator = OpenWrtUbusWifiPresenceCoordinator(hass=hass, entry=entry, client=client)

    assert coordinator.config_entry is entry

    with pytest.raises(ConfigEntryAuthFailed) as error:
        await coordinator._async_update_data()  # noqa: SLF001

    assert error.value.translation_domain == DOMAIN
    assert error.value.translation_key == "authentication_failed"


@pytest.mark.unit
@pytest.mark.parametrize("inventory_complete", [True, False])
async def test_coordinator_filters_unauthorized_stations(hass, inventory_complete: bool) -> None:
    """Test station filtering while preserving WiFi SSID inventory quality."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="router-office.example.com",
        data={
            CONF_HOST: "router-office.example.com",
            CONF_IP_ADDRESS: "",
            CONF_USE_HTTPS: False,
            CONF_PORT: None,
            CONF_VERIFY_SSL: False,
            CONF_ENDPOINT: "ubus",
            CONF_USERNAME: "root",
            CONF_PASSWORD: "secret",
        },
        options={CONF_TRACKING_MODE: "all", CONF_SCAN_INTERVAL: 30},
    )

    client = AsyncMock()
    client.normalize_mac = OpenWrtUbusClient.normalize_mac
    client.get_wifi_ssid_inventory.return_value = (
        {"wlan0": "HomeWiFi"},
        {"HomeWiFi", "DisabledWiFi"},
        inventory_complete,
    )
    client.get_iwinfo_ap_devices.return_value = ["wlan0"]
    client.get_iwinfo_assoclist.return_value = [
        {
            "mac": "11:22:33:44:55:66",
            "signal": -50,
            "authorized": True,
        },
        {
            "mac": "AA:BB:CC:DD:EE:FF",
            "signal": -46,
            "inactive": 11550,
            "authorized": False,
        },
    ]

    coordinator = OpenWrtUbusWifiPresenceCoordinator(hass=hass, entry=entry, client=client)
    devices = await coordinator._async_update_data()  # noqa: SLF001

    assert "11:22:33:44:55:66" in devices
    assert "AA:BB:CC:DD:EE:FF" not in devices
    assert coordinator.known_ssids == {"HomeWiFi", "DisabledWiFi"}
    assert coordinator.ssid_inventory_complete is inventory_complete


@pytest.mark.unit
async def test_coordinator_selects_freshest_duplicate_association(hass) -> None:
    """Test deterministic duplicate association selection within one refresh."""
    client = AsyncMock()
    client.normalize_mac = OpenWrtUbusClient.normalize_mac
    client.get_wifi_ssid_inventory.return_value = (
        {"wlan0": "HomeWiFi", "wlan1": "HomeWiFi"},
        {"HomeWiFi"},
        True,
    )
    client.get_iwinfo_ap_devices.return_value = ["wlan0", "wlan1"]
    client.get_iwinfo_assoclist.side_effect = [
        [{"mac": "11:22:33:44:55:66", "inactive": 5000, "signal": -35}],
        [{"mac": "11:22:33:44:55:66", "inactive": 1000, "signal": -70}],
    ]

    coordinator = OpenWrtUbusWifiPresenceCoordinator(hass=hass, entry=_fallback_test_entry(), client=client)
    devices = await coordinator._async_update_data()  # noqa: SLF001

    assert devices["11:22:33:44:55:66"].ap_device == "wlan1"
    assert devices["11:22:33:44:55:66"].inactive_ms == 1000
    assert devices["11:22:33:44:55:66"].signal_dbm == -70


@pytest.mark.unit
async def test_coordinator_uses_signal_and_ap_name_as_duplicate_tiebreakers(hass) -> None:
    """Test signal preference followed by deterministic AP ordering."""
    client = AsyncMock()
    client.normalize_mac = OpenWrtUbusClient.normalize_mac
    client.get_wifi_ssid_inventory.return_value = (
        {"wlan2": "HomeWiFi", "wlan1": "HomeWiFi", "wlan0": "HomeWiFi"},
        {"HomeWiFi"},
        True,
    )
    client.get_iwinfo_ap_devices.return_value = ["wlan2", "wlan1", "wlan0"]
    client.get_iwinfo_assoclist.side_effect = [
        [{"mac": "11:22:33:44:55:66", "inactive": 1000, "signal": -70}],
        [{"mac": "11:22:33:44:55:66", "inactive": 1000, "signal": -40}],
        [{"mac": "11:22:33:44:55:66", "inactive": 1000, "signal": -40}],
    ]

    coordinator = OpenWrtUbusWifiPresenceCoordinator(hass=hass, entry=_fallback_test_entry(), client=client)
    devices = await coordinator._async_update_data()  # noqa: SLF001

    assert devices["11:22:33:44:55:66"].ap_device == "wlan0"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("inactive", "signal"),
    [(-1, math.nan), (True, False), (math.inf, -math.inf)],
)
async def test_coordinator_discards_invalid_optional_station_metrics(
    hass,
    inactive: float | bool,
    signal: float | bool,
) -> None:
    """Test that invalid optional diagnostics do not affect presence."""
    client = AsyncMock()
    client.normalize_mac = OpenWrtUbusClient.normalize_mac
    client.get_wifi_ssid_inventory.return_value = ({"wlan0": "HomeWiFi"}, {"HomeWiFi"}, True)
    client.get_iwinfo_ap_devices.return_value = ["wlan0"]
    client.get_iwinfo_assoclist.return_value = [
        {"mac": "11:22:33:44:55:66", "inactive": inactive, "signal": signal},
    ]

    coordinator = OpenWrtUbusWifiPresenceCoordinator(hass=hass, entry=_fallback_test_entry(), client=client)
    devices = await coordinator._async_update_data()  # noqa: SLF001

    assert devices["11:22:33:44:55:66"].inactive_ms is None
    assert devices["11:22:33:44:55:66"].signal_dbm is None


def _fallback_test_entry() -> MockConfigEntry:
    """Build a config entry for SSID fallback completeness tests."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="router-fallback.example.com",
        data={
            CONF_HOST: "router-fallback.example.com",
            CONF_IP_ADDRESS: "",
            CONF_USE_HTTPS: False,
            CONF_PORT: None,
            CONF_VERIFY_SSL: False,
            CONF_ENDPOINT: "ubus",
            CONF_USERNAME: "root",
            CONF_PASSWORD: "secret",
        },
        options={CONF_TRACKING_MODE: "all", CONF_SCAN_INTERVAL: 30},
    )


@pytest.mark.unit
async def test_coordinator_marks_observed_fallback_inventory_complete(hass) -> None:
    """Test that a successfully resolved observed-only SSID is authoritative."""
    client = AsyncMock()
    client.normalize_mac = OpenWrtUbusClient.normalize_mac
    client.get_wifi_ssid_inventory.return_value = ({"wlan0": "HomeWiFi"}, {"HomeWiFi"}, True)
    client.get_iwinfo_ap_devices.return_value = ["wlan0", "wlan1"]
    client.get_iwinfo_assoclist.return_value = []
    client.get_iwinfo_ssid.return_value = "GuestWiFi"

    coordinator = OpenWrtUbusWifiPresenceCoordinator(hass=hass, entry=_fallback_test_entry(), client=client)
    await coordinator._async_update_data()  # noqa: SLF001

    assert coordinator.known_ssids == {"HomeWiFi", "GuestWiFi"}
    assert coordinator.ssid_inventory_complete is True
    client.get_iwinfo_ssid.assert_awaited_once_with("wlan1")


@pytest.mark.unit
async def test_coordinator_marks_missing_observed_fallback_incomplete(hass) -> None:
    """Test that an unresolved fallback SSID blocks destructive cleanup."""
    client = AsyncMock()
    client.normalize_mac = OpenWrtUbusClient.normalize_mac
    client.get_wifi_ssid_inventory.return_value = ({"wlan0": "HomeWiFi"}, {"HomeWiFi"}, True)
    client.get_iwinfo_ap_devices.return_value = ["wlan0", "wlan1"]
    client.get_iwinfo_assoclist.return_value = []
    client.get_iwinfo_ssid.return_value = None

    coordinator = OpenWrtUbusWifiPresenceCoordinator(hass=hass, entry=_fallback_test_entry(), client=client)
    await coordinator._async_update_data()  # noqa: SLF001

    assert coordinator.known_ssids == {"HomeWiFi"}
    assert coordinator.ssid_inventory_complete is False


@pytest.mark.unit
async def test_coordinator_fails_refresh_on_observed_fallback_error(hass) -> None:
    """Test that an iwinfo SSID communication error fails the coordinator refresh."""
    client = AsyncMock()
    client.normalize_mac = OpenWrtUbusClient.normalize_mac
    client.get_wifi_ssid_inventory.return_value = ({"wlan0": "HomeWiFi"}, {"HomeWiFi"}, True)
    client.get_iwinfo_ap_devices.return_value = ["wlan0", "wlan1"]
    client.get_iwinfo_assoclist.return_value = []
    client.get_iwinfo_ssid.side_effect = OpenWrtUbusCommunicationError("temporary failure")

    coordinator = OpenWrtUbusWifiPresenceCoordinator(hass=hass, entry=_fallback_test_entry(), client=client)

    with pytest.raises(UpdateFailed) as error:
        await coordinator._async_update_data()  # noqa: SLF001

    assert error.value.translation_domain == DOMAIN
    assert error.value.translation_key == "communication_failed"


@pytest.mark.unit
async def test_coordinator_translates_unexpected_client_error(hass) -> None:
    """Test generic ubus failures expose a translated Home Assistant error."""
    client = AsyncMock()
    client.normalize_mac = OpenWrtUbusClient.normalize_mac
    client.get_wifi_ssid_inventory.side_effect = OpenWrtUbusClientError("invalid response")
    coordinator = OpenWrtUbusWifiPresenceCoordinator(hass=hass, entry=_fallback_test_entry(), client=client)

    with pytest.raises(UpdateFailed) as error:
        await coordinator._async_update_data()  # noqa: SLF001

    assert error.value.translation_domain == DOMAIN
    assert error.value.translation_key == "unexpected_client_error"
