"""Tests for global OpenWrt WiFi device trackers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
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
    WifiPresenceDevice,
)
from custom_components.openwrt_ubus.device_tracker.manager import OpenWrtUbusWifiPresenceDeviceTrackerManager
from custom_components.openwrt_ubus.device_tracker.wifi_device import OpenWrtUbusWifiPresenceDeviceTracker
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.const import STATE_HOME, STATE_NOT_HOME, STATE_UNAVAILABLE
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.helpers.entity_registry import RegistryEntryDisabler, RegistryEntryHider

MAC = "11:22:33:44:55:66"
OTHER_MAC = "AA:BB:CC:DD:EE:FF"


def _alias_target(mac: str = MAC) -> TrackerTarget:
    """Return one stable alias target."""
    return TrackerTarget(
        entity_key="alias_living_room_sensor",
        tracker_type=TrackerTargetType.ALIAS,
        source=TrackerTargetSource.ALIAS,
        display_name="Living Room Sensor",
        mac=mac,
    )


def _mac_target(mac: str = MAC) -> TrackerTarget:
    """Return one dynamically discovered MAC target."""
    return TrackerTarget(
        entity_key=f"mac_{mac}",
        tracker_type=TrackerTargetType.MAC,
        source=TrackerTargetSource.ALL,
        display_name=mac.replace(":", ""),
        mac=mac,
    )


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


def _coordinator(
    entry: MockConfigEntry,
    *,
    targets: list[TrackerTarget],
    devices: list[WifiPresenceDevice] | None = None,
    successful: bool = True,
    updated_at: datetime | None = None,
) -> MagicMock:
    """Create a coordinator mock with realistic global-manager data."""
    coordinator = MagicMock(spec=OpenWrtUbusWifiPresenceCoordinator)
    coordinator.entry = entry
    coordinator.tracker_targets = {target.entity_key: target for target in targets}
    coordinator.data = {device.mac: device for device in devices or []}
    coordinator.last_update_success = successful
    coordinator.last_update_success_time = updated_at
    coordinator.async_add_listener.return_value = MagicMock()
    entry.runtime_data = OpenWrtUbusWifiPresenceRuntimeData(client=AsyncMock(), coordinator=coordinator)
    return coordinator


def _entity_platform(hass, entry: MockConfigEntry) -> EntityPlatform:
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


async def _register_with_platform(
    manager: OpenWrtUbusWifiPresenceDeviceTrackerManager,
    entry: MockConfigEntry,
    platform: EntityPlatform,
) -> MagicMock:
    """Register a config entry through a real EntityPlatform callback."""
    async_add_entities = MagicMock(wraps=platform._async_schedule_add_entities_for_entry)  # noqa: SLF001
    await manager.async_register_entry(entry, async_add_entities)
    await manager.hass.async_block_till_done()
    return async_add_entities


def _entity_id(hass, unique_id: str) -> str:
    """Resolve one tracker entity ID from the registry."""
    entity_id = er.async_get(hass).async_get_entity_id("device_tracker", DOMAIN, unique_id)
    assert entity_id is not None
    return entity_id


@pytest.mark.unit
async def test_global_tracker_selects_latest_activity_and_remembers_router(hass) -> None:
    """Test cross-router selection and runtime-only last-router memory."""
    first_entry = _entry(hass, "router-office.lan")
    second_entry = _entry(hass, "router-kitchen.lan")
    target = _alias_target()
    first_coordinator = _coordinator(
        first_entry,
        targets=[target],
        devices=[WifiPresenceDevice(MAC, "phy0-ap0", "MyNetwork", inactive_ms=5000, signal_dbm=-30)],
        updated_at=datetime(2026, 9, 1, 12, 0, 10, tzinfo=UTC),
    )
    second_coordinator = _coordinator(
        second_entry,
        targets=[target],
        devices=[WifiPresenceDevice(MAC, "phy1-ap0", "MyNetwork", inactive_ms=1000, signal_dbm=-70)],
        updated_at=datetime(2026, 9, 1, 12, 0, 8, tzinfo=UTC),
    )
    manager = OpenWrtUbusWifiPresenceDeviceTrackerManager(hass)
    first_platform = _entity_platform(hass, first_entry)
    second_platform = _entity_platform(hass, second_entry)

    await _register_with_platform(manager, first_entry, first_platform)
    await _register_with_platform(manager, second_entry, second_platform)

    entity_id = _entity_id(hass, target.entity_key)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["router"] == "router-kitchen.lan"
    assert state.attributes["ap_device"] == "phy1-ap0"
    assert len(first_platform.entities) == 1
    assert not second_platform.entities

    first_coordinator.data = {}
    second_coordinator.data = {}
    manager._handle_coordinator_update()  # noqa: SLF001
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_NOT_HOME
    assert state.attributes["router"] == "router-kitchen.lan"
    assert state.attributes["ssid"] is None
    assert state.attributes["ap_device"] is None

    fresh_manager = OpenWrtUbusWifiPresenceDeviceTrackerManager(hass)
    fresh_manager._coordinators = {  # noqa: SLF001
        first_entry.entry_id: first_coordinator,
        second_entry.entry_id: second_coordinator,
    }
    fresh_manager._rebuild_targets()  # noqa: SLF001
    assert fresh_manager.last_or_current_router_for_key(target.entity_key) is None

    await first_platform.async_reset()
    await second_platform.async_reset()


@pytest.mark.unit
async def test_partial_failure_never_uses_stale_presence(hass) -> None:
    """Test the home, unavailable, and not-home certainty matrix."""
    first_entry = _entry(hass, "router-office.lan")
    second_entry = _entry(hass, "router-kitchen.lan")
    target = _alias_target()
    first_coordinator = _coordinator(first_entry, targets=[target], devices=[])
    second_coordinator = _coordinator(
        second_entry,
        targets=[target],
        devices=[WifiPresenceDevice(MAC, "phy1-ap0", "MyNetwork")],
        successful=False,
    )
    manager = OpenWrtUbusWifiPresenceDeviceTrackerManager(hass)
    platform = _entity_platform(hass, first_entry)
    second_platform = _entity_platform(hass, second_entry)

    await _register_with_platform(manager, first_entry, platform)
    await _register_with_platform(manager, second_entry, second_platform)
    entity_id = _entity_id(hass, target.entity_key)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert manager.last_or_current_router_for_key(target.entity_key) is None

    first_coordinator.data = {MAC: WifiPresenceDevice(MAC, "phy0-ap0", "MyNetwork")}
    manager._handle_coordinator_update()  # noqa: SLF001
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["router"] == "router-office.lan"

    first_coordinator.data = {}
    manager._handle_coordinator_update()  # noqa: SLF001
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert manager.last_or_current_router_for_key(target.entity_key) == "router-office.lan"

    second_coordinator.last_update_success = True
    second_coordinator.data = {}
    manager._handle_coordinator_update()  # noqa: SLF001
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_NOT_HOME
    assert state.attributes["router"] == "router-office.lan"

    await platform.async_reset()
    await second_platform.async_reset()


@pytest.mark.unit
async def test_alias_conflict_is_stable_unavailable_and_logs_transitions(hass, caplog) -> None:
    """Test fail-safe behavior for the same alias mapped to different MACs."""
    first_entry = _entry(hass, "router-office.lan")
    second_entry = _entry(hass, "router-kitchen.lan")
    _coordinator(
        first_entry,
        targets=[_alias_target(MAC)],
        devices=[WifiPresenceDevice(MAC, "phy0-ap0", "MyNetwork")],
    )
    second_coordinator = _coordinator(second_entry, targets=[_alias_target(OTHER_MAC)], devices=[])
    manager = OpenWrtUbusWifiPresenceDeviceTrackerManager(hass)
    first_platform = _entity_platform(hass, first_entry)
    second_platform = _entity_platform(hass, second_entry)
    caplog.set_level("INFO")

    await _register_with_platform(manager, first_entry, first_platform)
    await _register_with_platform(manager, second_entry, second_platform)
    entity_id = _entity_id(hass, _alias_target().entity_key)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert manager.resolved_mac_for_key(_alias_target().entity_key) is None
    assert manager.last_or_current_router_for_key(_alias_target().entity_key) == "router-office.lan"
    conflict_messages = [
        record.message for record in caplog.records if "Conflicting global tracker alias" in record.message
    ]
    assert len(conflict_messages) == 1
    assert "router-office.lan=11:22:33:44:55:66" in conflict_messages[0]
    assert "router-kitchen.lan=AA:BB:CC:DD:EE:FF" in conflict_messages[0]

    manager._handle_coordinator_update()  # noqa: SLF001
    assert len([record for record in caplog.records if "Conflicting global tracker alias" in record.message]) == 1

    second_coordinator.tracker_targets = {_alias_target(MAC).entity_key: _alias_target(MAC)}
    manager._handle_coordinator_update()  # noqa: SLF001
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["mapped_mac"] == MAC
    assert any("conflict resolved" in record.message for record in caplog.records)

    await first_platform.async_reset()
    await second_platform.async_reset()


@pytest.mark.unit
async def test_alias_suppresses_plain_mac_target_across_routers(hass) -> None:
    """Test that global alias precedence is not limited to one config entry."""
    first_entry = _entry(hass, "router-office.lan")
    second_entry = _entry(hass, "router-kitchen.lan")
    alias_target = _alias_target()
    _coordinator(first_entry, targets=[alias_target], devices=[])
    _coordinator(second_entry, targets=[_mac_target()], devices=[])
    manager = OpenWrtUbusWifiPresenceDeviceTrackerManager(hass)

    await manager.async_register_entry(first_entry, MagicMock())
    await manager.async_register_entry(second_entry, MagicMock())

    assert set(manager._targets) == {alias_target.entity_key}  # noqa: SLF001


@pytest.mark.unit
def test_late_entity_add_callback_cannot_replace_current_entity(hass) -> None:
    """Test identity checks for delayed callbacks from an old platform."""
    manager = OpenWrtUbusWifiPresenceDeviceTrackerManager(hass)
    target = _alias_target()
    old_entity = OpenWrtUbusWifiPresenceDeviceTracker(
        manager=manager,
        owner_entry_id="old-entry",
        target=target,
    )
    replacement = OpenWrtUbusWifiPresenceDeviceTracker(
        manager=manager,
        owner_entry_id="new-entry",
        target=target,
    )
    manager._pending_entities_by_key[target.entity_key] = replacement  # noqa: SLF001

    manager.async_entity_added(replacement)
    manager._pending_entities_by_key[target.entity_key] = old_entity  # noqa: SLF001
    manager.async_entity_added(old_entity)
    manager.async_entity_removed(old_entity)

    assert manager._entities_by_key == {target.entity_key: replacement}  # noqa: SLF001
    assert not manager._pending_entities_by_key  # noqa: SLF001


@pytest.mark.unit
async def test_global_tracker_moves_from_disabled_config_entry_to_active_owner(hass) -> None:
    """Test that config-entry disabling does not strand a global tracker."""
    disabled_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="router-office.lan",
        data={CONF_HOST: "router-office.lan"},
        state=ConfigEntryState.LOADED,
        disabled_by=ConfigEntryDisabler.USER,
    )
    disabled_entry.add_to_hass(hass)
    active_entry = _entry(hass, "router-kitchen.lan")
    target = _alias_target()
    _coordinator(active_entry, targets=[target], devices=[])
    registry = er.async_get(hass)
    existing = registry.async_get_or_create(
        "device_tracker",
        DOMAIN,
        target.entity_key,
        config_entry=disabled_entry,
        disabled_by=RegistryEntryDisabler.CONFIG_ENTRY,
    )
    manager = OpenWrtUbusWifiPresenceDeviceTrackerManager(hass)

    await manager.async_register_entry(active_entry, MagicMock())

    moved = registry.async_get(existing.entity_id)
    assert moved is not None
    assert moved.config_entry_id == active_entry.entry_id
    assert not moved.disabled


@pytest.mark.unit
async def test_all_mode_tracker_can_disappear_and_reappear(hass) -> None:
    """Test registry visibility and entity lifecycle for dynamic MAC targets."""
    entry = _entry(hass, "router-office.lan")
    target = _mac_target()
    coordinator = _coordinator(
        entry,
        targets=[target],
        devices=[WifiPresenceDevice(MAC, "phy0-ap0", "MyNetwork")],
    )
    manager = OpenWrtUbusWifiPresenceDeviceTrackerManager(hass)
    platform = _entity_platform(hass, entry)

    await _register_with_platform(manager, entry, platform)
    entity_id = _entity_id(hass, target.entity_key)
    assert hass.states.get(entity_id).state == STATE_HOME

    coordinator.tracker_targets = {}
    coordinator.data = {}
    manager._handle_coordinator_update()  # noqa: SLF001
    await hass.async_block_till_done()

    hidden_entry = er.async_get(hass).async_get(entity_id)
    assert hidden_entry is not None
    assert hidden_entry.disabled_by == RegistryEntryDisabler.INTEGRATION
    assert hidden_entry.hidden_by == RegistryEntryHider.INTEGRATION
    assert hass.states.get(entity_id) is None
    assert not manager._entities_by_key  # noqa: SLF001

    coordinator.tracker_targets = {target.entity_key: target}
    coordinator.data = {MAC: WifiPresenceDevice(MAC, "phy0-ap0", "MyNetwork")}
    manager._handle_coordinator_update()  # noqa: SLF001
    await hass.async_block_till_done()

    restored_entry = er.async_get(hass).async_get(entity_id)
    assert restored_entry is not None
    assert not restored_entry.disabled
    assert restored_entry.hidden_by is None
    assert hass.states.get(entity_id).state == STATE_HOME
    assert set(manager._entities_by_key) == {target.entity_key}  # noqa: SLF001

    await platform.async_reset()
