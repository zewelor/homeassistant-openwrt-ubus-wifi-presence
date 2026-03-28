from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openwrt_ubus.api import OpenWrtUbusAuthenticationError
from custom_components.openwrt_ubus.const import (
    CONF_ENDPOINT,
    CONF_IP_ADDRESS,
    CONF_SCAN_INTERVAL,
    CONF_TRACKING_MODE,
    CONF_USE_HTTPS,
    CONF_WIRELESS_SOFTWARE,
    DOMAIN,
)
from custom_components.openwrt_ubus.coordinator import OpenWrtUbusWifiPresenceCoordinator
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.exceptions import ConfigEntryAuthFailed


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
            CONF_TRACKING_MODE: "known_or_alias",
            CONF_WIRELESS_SOFTWARE: "iwinfo",
            CONF_SCAN_INTERVAL: 30,
        },
    )

    client = AsyncMock()
    client.normalize_mac.side_effect = lambda value: value
    client.get_interface_to_ssid_mapping.side_effect = OpenWrtUbusAuthenticationError("invalid credentials")

    coordinator = OpenWrtUbusWifiPresenceCoordinator(hass=hass, entry=entry, client=client)

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()  # noqa: SLF001
