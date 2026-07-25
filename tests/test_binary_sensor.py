from __future__ import annotations

from unittest.mock import MagicMock

import pytest

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


def _prepare_manager_with_sensor(hass, *, successful: bool):
    """Prepare a manager containing one previously discovered WiFi SSID sensor."""
    manager = OpenWrtUbusSsidPresenceManager(hass)
    manager._owner_entry_id = "entry-1"  # noqa: SLF001
    manager._async_add_entities_by_entry["entry-1"] = MagicMock()  # noqa: SLF001
    manager._coordinators["entry-1"] = _mock_coordinator(successful=successful)  # noqa: SLF001

    sensor = OpenWrtUbusSsidPresenceBinarySensor("Guest WiFi")
    entity_registry = er.async_get(hass)
    registry_entry = entity_registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        sensor.unique_id,
        suggested_object_id="openwrt_wifi_guest_wifi_presence",
    )
    manager._entities_by_ssid[sensor.ssid] = sensor  # noqa: SLF001
    return manager, entity_registry, registry_entry


@pytest.mark.unit
def test_removes_sensor_when_wifi_ssid_is_no_longer_reported(hass) -> None:
    """Test removal after every router confirms the WiFi SSID disappeared."""
    manager, entity_registry, registry_entry = _prepare_manager_with_sensor(hass, successful=True)

    manager._sync_ssid_entities()  # noqa: SLF001

    assert "Guest WiFi" not in manager._entities_by_ssid  # noqa: SLF001
    assert entity_registry.async_get(registry_entry.entity_id) is None


@pytest.mark.unit
def test_keeps_sensor_when_router_update_failed(hass) -> None:
    """Test that a transient router failure cannot remove a WiFi SSID sensor."""
    manager, entity_registry, registry_entry = _prepare_manager_with_sensor(hass, successful=False)

    manager._sync_ssid_entities()  # noqa: SLF001

    assert "Guest WiFi" in manager._entities_by_ssid  # noqa: SLF001
    assert entity_registry.async_get(registry_entry.entity_id) is registry_entry
