"""Lifecycle tests for global OpenWrt WiFi device trackers."""

from __future__ import annotations

from datetime import timedelta
from logging import getLogger
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openwrt_ubus.const import CONF_HOST, DOMAIN
from custom_components.openwrt_ubus.coordinator import OpenWrtUbusWifiPresenceCoordinator
from custom_components.openwrt_ubus.data import (
    OpenWrtUbusWifiPresenceRuntimeData,
    TrackerTarget,
    TrackerTargetSource,
    TrackerTargetType,
)
from custom_components.openwrt_ubus.device_tracker.manager import OpenWrtUbusWifiPresenceDeviceTrackerManager
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import EntityPlatform

MAC = "11:22:33:44:55:66"


def _entry(hass, host: str) -> MockConfigEntry:
    """Create one loaded OpenWrt config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=host,
        data={CONF_HOST: host},
        state=ConfigEntryState.LOADED,
    )
    entry.add_to_hass(hass)
    return entry


def _target() -> TrackerTarget:
    """Return one global alias target."""
    return TrackerTarget(
        entity_key="alias_living_room_sensor",
        tracker_type=TrackerTargetType.ALIAS,
        source=TrackerTargetSource.ALIAS,
        display_name="Living Room Sensor",
        mac=MAC,
    )


def _coordinator(entry: MockConfigEntry, target: TrackerTarget) -> MagicMock:
    """Attach one successful coordinator mock to a config entry."""
    coordinator = MagicMock(spec=OpenWrtUbusWifiPresenceCoordinator)
    coordinator.entry = entry
    coordinator.tracker_targets = {target.entity_key: target}
    coordinator.data = {}
    coordinator.last_update_success = True
    coordinator.last_update_success_time = None
    coordinator.async_add_listener.return_value = MagicMock()
    entry.runtime_data = OpenWrtUbusWifiPresenceRuntimeData(client=AsyncMock(), coordinator=coordinator)
    return coordinator


def _platform(hass, entry: MockConfigEntry) -> EntityPlatform:
    """Create a real Home Assistant device tracker platform."""
    platform = EntityPlatform(
        hass=hass,
        logger=getLogger(__name__),
        domain="device_tracker",
        platform_name=DOMAIN,
        platform=None,
        scan_interval=timedelta(seconds=30),
        entity_namespace=None,
    )
    platform.config_entry = entry
    return platform


async def _register(
    manager: OpenWrtUbusWifiPresenceDeviceTrackerManager,
    entry: MockConfigEntry,
    platform: EntityPlatform,
) -> None:
    """Register an entry through a real EntityPlatform callback."""
    async_add_entities = MagicMock(wraps=platform._async_schedule_add_entities_for_entry)  # noqa: SLF001
    await manager.async_register_entry(entry, async_add_entities)
    await manager.hass.async_block_till_done()


@pytest.mark.unit
@pytest.mark.parametrize("unregister_first", [False, True])
async def test_owner_transfer_handles_both_unload_callback_orders(hass, unregister_first: bool) -> None:
    """Test replacement regardless of unload callback ordering."""
    first_entry = _entry(hass, "router-office.lan")
    second_entry = _entry(hass, "router-kitchen.lan")
    target = _target()
    _coordinator(first_entry, target)
    _coordinator(second_entry, target)
    manager = OpenWrtUbusWifiPresenceDeviceTrackerManager(hass)
    first_platform = _platform(hass, first_entry)
    second_platform = _platform(hass, second_entry)

    await _register(manager, first_entry, first_platform)
    await _register(manager, second_entry, second_platform)
    entity_id = er.async_get(hass).async_get_entity_id("device_tracker", DOMAIN, target.entity_key)
    assert entity_id is not None
    first_entity = next(iter(first_platform.entities.values()))

    if unregister_first:
        manager._async_unregister_entry(first_entry.entry_id)  # noqa: SLF001
        await hass.async_block_till_done()
        assert not second_platform.entities
        await first_platform.async_reset()
        await hass.async_block_till_done()
    else:
        await first_platform.async_reset()
        assert not second_platform.entities
        manager._async_unregister_entry(first_entry.entry_id)  # noqa: SLF001
        await hass.async_block_till_done()

    assert len(second_platform.entities) == 1
    second_entity = next(iter(second_platform.entities.values()))
    assert second_entity is not first_entity
    assert second_entity.entity_id == entity_id
    registry_entry = er.async_get(hass).async_get(entity_id)
    assert registry_entry is not None
    assert registry_entry.config_entry_id == second_entry.entry_id

    await second_platform.async_reset()
