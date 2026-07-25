from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openwrt_ubus.binary_sensor import (
    OpenWrtUbusSsidPresenceBinarySensor,
    OpenWrtUbusSsidPresenceManager,
)
from custom_components.openwrt_ubus.const import DOMAIN
from custom_components.openwrt_ubus.coordinator import OpenWrtUbusWifiPresenceCoordinator
from homeassistant.helpers import entity_registry as er


def _setup_manager(hass, *, current_ssids: set[str], successful: bool):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="router.example.com")
    entry.add_to_hass(hass)

    coordinator = MagicMock(spec=OpenWrtUbusWifiPresenceCoordinator)
    coordinator.last_update_success = successful
    coordinator.known_ssids = current_ssids
    coordinator.data = {}

    manager = OpenWrtUbusSsidPresenceManager(hass)
    manager._owner_entry_id = entry.entry_id  # noqa: SLF001
    async_add_entities = MagicMock()
    manager._async_add_entities_by_entry[entry.entry_id] = async_add_entities  # noqa: SLF001
    manager._coordinators[entry.entry_id] = coordinator  # noqa: SLF001

    old_sensor = OpenWrtUbusSsidPresenceBinarySensor("Guest WiFi")
    manager._entities_by_ssid[old_sensor.ssid] = old_sensor  # noqa: SLF001
    entity_registry = er.async_get(hass)
    old_entry = entity_registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        old_sensor.unique_id,
        config_entry=entry,
    )
    return manager, async_add_entities, entity_registry, old_entry


@pytest.mark.unit
def test_replaces_sensor_after_wifi_ssid_rename(hass) -> None:
    manager, async_add_entities, entity_registry, old_entry = _setup_manager(
        hass, current_ssids={"Private WiFi"}, successful=True
    )

    manager._sync_ssid_entities()  # noqa: SLF001

    assert entity_registry.async_get(old_entry.entity_id) is None
    assert set(manager._entities_by_ssid) == {"Private WiFi"}  # noqa: SLF001
    added_entities = async_add_entities.call_args.args[0]
    assert [entity.ssid for entity in added_entities] == ["Private WiFi"]


@pytest.mark.unit
@pytest.mark.parametrize(("successful", "missing_coordinator"), [(False, False), (True, True)])
def test_keeps_sensor_until_data_is_complete(hass, successful: bool, missing_coordinator: bool) -> None:
    manager, async_add_entities, entity_registry, old_entry = _setup_manager(
        hass, current_ssids=set(), successful=successful
    )
    if missing_coordinator:
        MockConfigEntry(domain=DOMAIN, unique_id="other.example.com").add_to_hass(hass)

    manager._sync_ssid_entities()  # noqa: SLF001

    assert entity_registry.async_get(old_entry.entity_id) is old_entry
    assert set(manager._entities_by_ssid) == {"Guest WiFi"}  # noqa: SLF001
    async_add_entities.assert_not_called()
