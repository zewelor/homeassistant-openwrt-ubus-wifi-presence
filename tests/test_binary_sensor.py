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


def _mock_coordinator(*, successful: bool) -> OpenWrtUbusWifiPresenceCoordinator:
    """Return a coordinator mock with no currently reported WiFi SSIDs."""
    coordinator = MagicMock(spec=OpenWrtUbusWifiPresenceCoordinator)
    coordinator.last_update_success = successful
    coordinator.known_ssids = set()
    coordinator.data = {}
    return coordinator


def _prepare_manager_with_registry_sensor(hass, *, successful: bool, track_runtime: bool):
    """Prepare a manager and one previously discovered WiFi SSID registry entry."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="router.example.com")
    entry.add_to_hass(hass)

    manager = OpenWrtUbusSsidPresenceManager(hass)
    manager._owner_entry_id = entry.entry_id  # noqa: SLF001
    manager._async_add_entities_by_entry[entry.entry_id] = MagicMock()  # noqa: SLF001
    manager._coordinators[entry.entry_id] = _mock_coordinator(successful=successful)  # noqa: SLF001

    sensor = OpenWrtUbusSsidPresenceBinarySensor("Guest WiFi")
    assert sensor.unique_id is not None
    entity_registry = er.async_get(hass)
    registry_entry = entity_registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        sensor.unique_id,
        config_entry=entry,
        suggested_object_id="openwrt_wifi_guest_wifi_presence",
    )
    if track_runtime:
        manager._entities_by_ssid[sensor.ssid] = sensor  # noqa: SLF001
    return manager, entity_registry, registry_entry


@pytest.mark.unit
def test_removes_runtime_sensor_when_wifi_ssid_is_no_longer_reported(hass) -> None:
    """Test removal after every router confirms the WiFi SSID disappeared."""
    manager, entity_registry, registry_entry = _prepare_manager_with_registry_sensor(
        hass, successful=True, track_runtime=True
    )

    manager._sync_ssid_entities()  # noqa: SLF001

    assert "Guest WiFi" not in manager._entities_by_ssid  # noqa: SLF001
    assert entity_registry.async_get(registry_entry.entity_id) is None


@pytest.mark.unit
def test_removes_registry_only_sensor_after_restart(hass) -> None:
    """Test cleanup when the WiFi SSID disappeared while Home Assistant was off."""
    manager, entity_registry, registry_entry = _prepare_manager_with_registry_sensor(
        hass, successful=True, track_runtime=False
    )

    manager._sync_ssid_entities()  # noqa: SLF001

    assert entity_registry.async_get(registry_entry.entity_id) is None


@pytest.mark.unit
def test_keeps_sensor_when_router_update_failed(hass) -> None:
    """Test that a transient router failure cannot remove a WiFi SSID sensor."""
    manager, entity_registry, registry_entry = _prepare_manager_with_registry_sensor(
        hass, successful=False, track_runtime=True
    )

    manager._sync_ssid_entities()  # noqa: SLF001

    assert "Guest WiFi" in manager._entities_by_ssid  # noqa: SLF001
    assert entity_registry.async_get(registry_entry.entity_id) is registry_entry
