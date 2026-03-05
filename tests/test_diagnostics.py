from __future__ import annotations

from types import SimpleNamespace

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openwrt_ubus.const import DOMAIN
from custom_components.openwrt_ubus.data import (
    TrackerTarget,
    TrackerTargetSource,
    TrackerTargetType,
    WifiPresenceDevice,
)
from custom_components.openwrt_ubus.diagnostics import async_get_config_entry_diagnostics


async def test_diagnostics_redacts_sensitive_network_fields(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="ap-michal.x1.lan",
        data={
            "host": "ap-michal.x1.lan",
            "username": "root",
            "password": "secret",
            "ip_address": "192.168.1.1",
        },
    )

    coordinator = SimpleNamespace(
        data={
            "AA:BB:CC:DD:EE:FF": WifiPresenceDevice(
                mac="AA:BB:CC:DD:EE:FF",
                hostname="my_phone",
                ip_address="192.168.1.20",
                ap_device="wlan0",
                ssid="Home",
            )
        },
        tracker_targets={
            "alias_my_phone": TrackerTarget(
                entity_key="alias_my_phone",
                tracker_type=TrackerTargetType.ALIAS,
                source=TrackerTargetSource.ALIAS,
                display_name="my_phone",
                mac="AA:BB:CC:DD:EE:FF",
            )
        },
        tracking_mode="known_or_alias",
        alias_mapping_file="/config/openwrt_ubus_aliases.yaml",
    )
    entry.runtime_data = SimpleNamespace(coordinator=coordinator)

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["entry"]["data"]["password"] == "**REDACTED**"
    assert result["devices"][0]["mac"] == "**REDACTED**"
    assert result["devices"][0]["hostname"] == "**REDACTED**"
    assert result["devices"][0]["ip_address"] == "**REDACTED**"
    assert result["tracker_targets"]["alias_my_phone"]["mac"] == "**REDACTED**"
