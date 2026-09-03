from __future__ import annotations

import json
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


def _assert_empty_runtime_diagnostics(result: dict) -> None:
    """Assert diagnostics keep their shape without coordinator runtime data."""
    assert result["devices"] == []
    assert result["tracking_mode"] == "known_or_alias"
    assert result["mapping_source"] == "hybrid"
    assert result["alias_mapping_file"] == ""
    assert result["alias_mapping_summary"] == {}
    assert result["tracker_targets"] == []


async def test_diagnostics_redacts_sensitive_network_fields(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="OpenWrt Ubus WiFi Presence (ap-livingroom.example.com)",
        unique_id="11:22:33:44:55:66",
        data={
            "host": "ap-livingroom.example.com",
            "username": "root",
            "password": "secret",
            "ip_address": "192.168.1.1",
        },
    )

    coordinator = SimpleNamespace(
        data={
            "AA:BB:CC:DD:EE:FF": WifiPresenceDevice(
                mac="AA:BB:CC:DD:EE:FF",
                ap_device="wlan0",
                ssid="Home",
            )
        },
        tracker_targets={
            "alias_living_room_sensor": TrackerTarget(
                entity_key="alias_living_room_sensor",
                tracker_type=TrackerTargetType.ALIAS,
                source=TrackerTargetSource.ALIAS,
                display_name="living_room_sensor",
                mac="AA:BB:CC:DD:EE:FF",
            )
        },
        tracking_mode="known_or_alias",
        alias_mapping_file="/config/openwrt_ubus_aliases.yaml",
    )
    entry.runtime_data = SimpleNamespace(coordinator=coordinator)

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["entry"]["data"]["password"] == "**REDACTED**"
    assert result["entry"]["data"]["ip_address"] == "**REDACTED**"
    assert result["devices"][0]["mac"] == "**REDACTED**"
    assert result["tracker_targets"][0]["mac"] == "**REDACTED**"

    serialized = json.dumps(result, sort_keys=True)
    for sensitive_value in (
        "ap-livingroom.example.com",
        "192.168.1.1",
        "AA:BB:CC:DD:EE:FF",
        "alias_living_room_sensor",
        "living_room_sensor",
        "Home",
        "wlan0",
        "/config/openwrt_ubus_aliases.yaml",
        "secret",
    ):
        assert sensitive_value not in serialized


async def test_diagnostics_handles_missing_runtime_data(hass) -> None:
    """Test diagnostics remain available before runtime data exists."""
    entry = MockConfigEntry(domain=DOMAIN, data={})

    result = await async_get_config_entry_diagnostics(hass, entry)

    _assert_empty_runtime_diagnostics(result)


async def test_diagnostics_handles_missing_coordinator(hass) -> None:
    """Test diagnostics remain available without a coordinator."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.runtime_data = SimpleNamespace()

    result = await async_get_config_entry_diagnostics(hass, entry)

    _assert_empty_runtime_diagnostics(result)


async def test_diagnostics_handles_none_coordinator_data(hass) -> None:
    """Test diagnostics treat absent coordinator data as an empty collection."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.runtime_data = SimpleNamespace(coordinator=SimpleNamespace(data=None, tracker_targets={}))

    result = await async_get_config_entry_diagnostics(hass, entry)

    _assert_empty_runtime_diagnostics(result)
