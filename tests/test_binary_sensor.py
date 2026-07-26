from __future__ import annotations

from datetime import timedelta
from logging import getLogger
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openwrt_ubus.binary_sensor import (
    OpenWrtUbusSsidPresenceBinarySensor,
    OpenWrtUbusSsidPresenceManager,
)
from custom_components.openwrt_ubus.const import DOMAIN
from custom_components.openwrt_ubus.coordinator import OpenWrtUbusWifiPresenceCoordinator
from homeassistant.config_entries import ConfigEntryDisabler
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.helpers.entity_registry import RegistryEntryDisabler


def _setup_manager(
    hass,
    *,
    current_ssids: set[str],
    successful: bool = True,
    inventory_complete: bool = True,
    existing_ssid: str | None = "Guest WiFi",
):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="router.example.com")
    entry.add_to_hass(hass)

    coordinator = MagicMock(spec=OpenWrtUbusWifiPresenceCoordinator)
    coordinator.last_update_success = successful
    coordinator.ssid_inventory_complete = inventory_complete
    coordinator.known_ssids = current_ssids
    coordinator.data = {}

    manager = OpenWrtUbusSsidPresenceManager(hass)
    hass.data.setdefault(DOMAIN, {})["ssid_presence_manager"] = manager
    manager._owner_entry_id = entry.entry_id  # noqa: SLF001
    async_add_entities = MagicMock()
    manager._async_add_entities_by_entry[entry.entry_id] = async_add_entities  # noqa: SLF001
    manager._coordinators[entry.entry_id] = coordinator  # noqa: SLF001

    entity_registry = er.async_get(hass)
    existing_sensor = None
    existing_entry = None
    if existing_ssid is not None:
        existing_sensor = OpenWrtUbusSsidPresenceBinarySensor(existing_ssid)
        existing_sensor.hass = hass
        manager.async_entity_added(existing_sensor)
        existing_entry = entity_registry.async_get_or_create(
            "binary_sensor",
            DOMAIN,
            existing_sensor.unique_id,
            config_entry=entry,
        )

    return manager, async_add_entities, entity_registry, existing_entry, entry, existing_sensor


def _setup_entity_platform(hass, entry) -> EntityPlatform:
    """Create a real Home Assistant entity platform for lifecycle tests."""
    platform = EntityPlatform(
        hass=hass,
        logger=getLogger(__name__),
        domain="binary_sensor",
        platform_name=DOMAIN,
        platform=None,
        scan_interval=timedelta(seconds=30),
        entity_namespace=None,
    )
    platform.config_entry = entry
    return platform


def _coordinator_with_ssids(ssids: set[str]) -> MagicMock:
    """Create a successful coordinator mock with an authoritative SSID inventory."""
    coordinator = MagicMock(spec=OpenWrtUbusWifiPresenceCoordinator)
    coordinator.last_update_success = True
    coordinator.ssid_inventory_complete = True
    coordinator.known_ssids = ssids
    coordinator.data = {}
    return coordinator


@pytest.mark.unit
def test_ssid_entity_uses_coordinator_updates_instead_of_entity_polling() -> None:
    entity = OpenWrtUbusSsidPresenceBinarySensor("Home WiFi")

    assert entity.should_poll is False


@pytest.mark.unit
async def test_replaces_sensor_after_wifi_ssid_rename(hass) -> None:
    manager, async_add_entities, entity_registry, old_entry, entry, old_sensor = _setup_manager(
        hass, current_ssids={"Private WiFi"}
    )
    assert old_entry is not None
    assert old_sensor is not None
    unrelated_entry = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        old_entry.unique_id,
        config_entry=entry,
    )

    manager._sync_ssid_entities()  # noqa: SLF001

    assert entity_registry.async_get(old_entry.entity_id) is None
    assert entity_registry.async_get(unrelated_entry.entity_id) is unrelated_entry
    assert set(manager._entities_by_ssid) == {"Guest WiFi"}  # noqa: SLF001
    assert manager._pending_ssids == {"Private WiFi"}  # noqa: SLF001
    added_entity = async_add_entities.call_args.args[0][0]

    await old_sensor.async_will_remove_from_hass()
    added_entity.hass = hass
    await added_entity.async_added_to_hass()

    assert set(manager._entities_by_ssid) == {"Private WiFi"}  # noqa: SLF001
    assert not manager._pending_ssids  # noqa: SLF001


@pytest.mark.unit
async def test_removes_sensor_after_wifi_ssid_deletion(hass) -> None:
    manager, async_add_entities, entity_registry, old_entry, _, old_sensor = _setup_manager(hass, current_ssids=set())
    assert old_entry is not None
    assert old_sensor is not None

    manager._sync_ssid_entities()  # noqa: SLF001

    assert entity_registry.async_get(old_entry.entity_id) is None
    assert set(manager._entities_by_ssid) == {"Guest WiFi"}  # noqa: SLF001
    async_add_entities.assert_not_called()

    await old_sensor.async_will_remove_from_hass()

    assert not manager._entities_by_ssid  # noqa: SLF001


@pytest.mark.unit
@pytest.mark.parametrize(
    ("successful", "inventory_complete", "missing_coordinator"),
    [(False, True, False), (True, False, False), (True, True, True)],
)
def test_keeps_sensor_until_wifi_ssid_inventory_is_authoritative(
    hass,
    successful: bool,
    inventory_complete: bool,
    missing_coordinator: bool,
) -> None:
    manager, async_add_entities, entity_registry, old_entry, _, _ = _setup_manager(
        hass,
        current_ssids=set(),
        successful=successful,
        inventory_complete=inventory_complete,
    )
    assert old_entry is not None
    if missing_coordinator:
        MockConfigEntry(domain=DOMAIN, unique_id="other.example.com").add_to_hass(hass)

    manager._sync_ssid_entities()  # noqa: SLF001

    assert entity_registry.async_get(old_entry.entity_id) is old_entry
    assert set(manager._entities_by_ssid) == {"Guest WiFi"}  # noqa: SLF001
    async_add_entities.assert_not_called()


@pytest.mark.unit
def test_removes_stale_ssid_owned_by_disabled_config_entry(hass) -> None:
    disabled_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="disabled.example.com",
        disabled_by=ConfigEntryDisabler.USER,
    )
    active_entry = MockConfigEntry(domain=DOMAIN, unique_id="active.example.com")
    disabled_entry.add_to_hass(hass)
    active_entry.add_to_hass(hass)

    manager = OpenWrtUbusSsidPresenceManager(hass)
    manager._owner_entry_id = active_entry.entry_id  # noqa: SLF001
    manager._async_add_entities_by_entry[active_entry.entry_id] = MagicMock()  # noqa: SLF001
    manager._coordinators[active_entry.entry_id] = _coordinator_with_ssids(set())  # noqa: SLF001

    entity_registry = er.async_get(hass)
    stale_sensor = OpenWrtUbusSsidPresenceBinarySensor("Old WiFi")
    stale_entry = entity_registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        stale_sensor.unique_id,
        config_entry=disabled_entry,
    )
    unrelated_entry = entity_registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        "unrelated_binary_sensor",
        config_entry=disabled_entry,
    )

    manager._sync_ssid_entities()  # noqa: SLF001

    assert entity_registry.async_get(stale_entry.entity_id) is None
    assert entity_registry.async_get(unrelated_entry.entity_id) is unrelated_entry


@pytest.mark.unit
async def test_tracks_entity_only_after_home_assistant_adds_it(hass) -> None:
    manager, async_add_entities, _, _, _, _ = _setup_manager(
        hass,
        current_ssids={"Home WiFi"},
        existing_ssid=None,
    )

    manager._sync_ssid_entities()  # noqa: SLF001
    manager._sync_ssid_entities()  # noqa: SLF001

    async_add_entities.assert_called_once()
    entity = async_add_entities.call_args.args[0][0]
    assert not manager._entities_by_ssid  # noqa: SLF001
    assert manager._pending_ssids == {"Home WiFi"}  # noqa: SLF001

    entity.hass = hass
    await entity.async_added_to_hass()

    assert manager._entities_by_ssid == {"Home WiFi": entity}  # noqa: SLF001
    assert not manager._pending_ssids  # noqa: SLF001


@pytest.mark.unit
def test_late_removal_callback_does_not_drop_replacement(hass) -> None:
    manager = OpenWrtUbusSsidPresenceManager(hass)
    old_entity = OpenWrtUbusSsidPresenceBinarySensor("Home WiFi")
    replacement = OpenWrtUbusSsidPresenceBinarySensor("Home WiFi")

    manager.async_entity_added(old_entity)
    manager.async_entity_added(replacement)
    manager.async_entity_removed(old_entity)

    assert manager._entities_by_ssid == {"Home WiFi": replacement}  # noqa: SLF001


@pytest.mark.unit
async def test_disabled_entity_moves_only_when_owner_changes(hass) -> None:
    first_entry = MockConfigEntry(domain=DOMAIN, unique_id="first.example.com")
    second_entry = MockConfigEntry(domain=DOMAIN, unique_id="second.example.com")
    first_entry.add_to_hass(hass)
    second_entry.add_to_hass(hass)

    manager = OpenWrtUbusSsidPresenceManager(hass)
    hass.data.setdefault(DOMAIN, {})["ssid_presence_manager"] = manager
    manager._owner_entry_id = second_entry.entry_id  # noqa: SLF001
    manager._coordinators[second_entry.entry_id] = _coordinator_with_ssids({"Home WiFi"})  # noqa: SLF001

    platform = _setup_entity_platform(hass, second_entry)
    async_add_entities = MagicMock(wraps=platform._async_schedule_add_entities_for_entry)  # noqa: SLF001
    manager._async_add_entities_by_entry[second_entry.entry_id] = async_add_entities  # noqa: SLF001

    entity_registry = er.async_get(hass)
    sensor = OpenWrtUbusSsidPresenceBinarySensor("Home WiFi")
    registry_entry = entity_registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        sensor.unique_id,
        config_entry=first_entry,
        disabled_by=RegistryEntryDisabler.USER,
    )

    manager._sync_ssid_entities()  # noqa: SLF001
    await hass.async_block_till_done()

    async_add_entities.assert_called_once()
    assert not manager._entities_by_ssid  # noqa: SLF001
    assert not manager._pending_ssids  # noqa: SLF001
    assert not platform.entities
    assert platform._async_polling_timer is None  # noqa: SLF001

    moved_entry = entity_registry.async_get(registry_entry.entity_id)
    assert moved_entry is not None
    assert moved_entry.config_entry_id == second_entry.entry_id
    assert moved_entry.disabled

    manager._sync_ssid_entities()  # noqa: SLF001
    await hass.async_block_till_done()

    async_add_entities.assert_called_once()


@pytest.mark.unit
async def test_config_entry_disabled_entity_is_enabled_for_new_owner(hass) -> None:
    first_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="first.example.com",
        disabled_by=ConfigEntryDisabler.USER,
    )
    second_entry = MockConfigEntry(domain=DOMAIN, unique_id="second.example.com")
    first_entry.add_to_hass(hass)
    second_entry.add_to_hass(hass)

    manager = OpenWrtUbusSsidPresenceManager(hass)
    hass.data.setdefault(DOMAIN, {})["ssid_presence_manager"] = manager
    manager._owner_entry_id = second_entry.entry_id  # noqa: SLF001
    manager._coordinators[second_entry.entry_id] = _coordinator_with_ssids({"Home WiFi"})  # noqa: SLF001

    platform = _setup_entity_platform(hass, second_entry)
    async_add_entities = MagicMock(wraps=platform._async_schedule_add_entities_for_entry)  # noqa: SLF001
    manager._async_add_entities_by_entry[second_entry.entry_id] = async_add_entities  # noqa: SLF001

    entity_registry = er.async_get(hass)
    sensor = OpenWrtUbusSsidPresenceBinarySensor("Home WiFi")
    registry_entry = entity_registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        sensor.unique_id,
        config_entry=first_entry,
        disabled_by=RegistryEntryDisabler.CONFIG_ENTRY,
    )

    manager._sync_ssid_entities()  # noqa: SLF001
    await hass.async_block_till_done()

    async_add_entities.assert_called_once()
    assert not manager._pending_ssids  # noqa: SLF001
    assert len(platform.entities) == 1
    entity = next(iter(platform.entities.values()))
    assert manager._entities_by_ssid == {"Home WiFi": entity}  # noqa: SLF001
    assert platform._async_polling_timer is None  # noqa: SLF001

    moved_entry = entity_registry.async_get(registry_entry.entity_id)
    assert moved_entry is not None
    assert moved_entry.config_entry_id == second_entry.entry_id
    assert not moved_entry.disabled

    await platform.async_reset()


@pytest.mark.unit
async def test_owner_transfer_waits_until_old_platform_unloads(hass) -> None:
    first_entry = MockConfigEntry(domain=DOMAIN, unique_id="first.example.com")
    second_entry = MockConfigEntry(domain=DOMAIN, unique_id="second.example.com")
    first_entry.add_to_hass(hass)
    second_entry.add_to_hass(hass)

    manager = OpenWrtUbusSsidPresenceManager(hass)
    hass.data.setdefault(DOMAIN, {})["ssid_presence_manager"] = manager
    first_platform = _setup_entity_platform(hass, first_entry)
    second_platform = _setup_entity_platform(hass, second_entry)
    first_add_entities = MagicMock(wraps=first_platform._async_schedule_add_entities_for_entry)  # noqa: SLF001
    second_add_entities = MagicMock(wraps=second_platform._async_schedule_add_entities_for_entry)  # noqa: SLF001
    manager._async_add_entities_by_entry = {  # noqa: SLF001
        first_entry.entry_id: first_add_entities,
        second_entry.entry_id: second_add_entities,
    }
    manager._owner_entry_id = first_entry.entry_id  # noqa: SLF001
    manager._coordinators = {  # noqa: SLF001
        first_entry.entry_id: _coordinator_with_ssids({"Home WiFi"}),
        second_entry.entry_id: _coordinator_with_ssids({"Home WiFi"}),
    }

    manager._sync_ssid_entities()  # noqa: SLF001
    await hass.async_block_till_done()

    first_add_entities.assert_called_once()
    second_add_entities.assert_not_called()
    assert len(first_platform.entities) == 1
    first_entity = next(iter(first_platform.entities.values()))
    assert manager._entities_by_ssid == {"Home WiFi": first_entity}  # noqa: SLF001
    assert first_platform._async_polling_timer is None  # noqa: SLF001

    await first_platform.async_reset()

    assert not manager._entities_by_ssid  # noqa: SLF001
    assert not first_platform.entities
    second_add_entities.assert_not_called()

    manager._async_unregister_entry(first_entry.entry_id)  # noqa: SLF001
    await hass.async_block_till_done()

    assert manager._owner_entry_id == second_entry.entry_id  # noqa: SLF001
    second_add_entities.assert_called_once()
    assert len(second_platform.entities) == 1
    second_entity = next(iter(second_platform.entities.values()))
    assert manager._entities_by_ssid == {"Home WiFi": second_entity}  # noqa: SLF001
    assert second_entity is not first_entity
    assert second_platform._async_polling_timer is None  # noqa: SLF001

    registry_entry = er.async_get(hass).async_get(second_entity.entity_id)
    assert registry_entry is not None
    assert registry_entry.config_entry_id == second_entry.entry_id

    await second_platform.async_reset()
