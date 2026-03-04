"""Device tracker platform for OpenWrt Ubus WiFi Presence."""

from __future__ import annotations

from custom_components.openwrt_ubus_wifi_presence.const import CONF_HOST, DOMAIN
from custom_components.openwrt_ubus_wifi_presence.data import OpenWrtUbusWifiPresenceConfigEntry
from custom_components.openwrt_ubus_wifi_presence.device_tracker.wifi_device import OpenWrtUbusWifiPresenceDeviceTracker
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass,
    entry: OpenWrtUbusWifiPresenceConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiFi device tracker entities for one config entry."""
    coordinator = entry.runtime_data.coordinator
    host = entry.data[CONF_HOST]
    known_entities: dict[str, OpenWrtUbusWifiPresenceDeviceTracker] = {}

    # Restore registry-backed entities so disconnected devices still exist as not_home.
    entity_registry = er.async_get(hass)
    prefix = f"{host}_"
    for existing in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        if existing.domain != "device_tracker" or existing.platform != DOMAIN or not existing.unique_id:
            continue
        if not existing.unique_id.startswith(prefix):
            continue

        mac = existing.unique_id.removeprefix(prefix)
        known_entities[mac] = OpenWrtUbusWifiPresenceDeviceTracker(coordinator, entry, mac)

    def _build_entities(macs: set[str]) -> list[OpenWrtUbusWifiPresenceDeviceTracker]:
        new_entities: list[OpenWrtUbusWifiPresenceDeviceTracker] = []
        for mac in sorted(macs):
            if mac in known_entities:
                continue
            known_entities[mac] = OpenWrtUbusWifiPresenceDeviceTracker(coordinator, entry, mac)
            new_entities.append(known_entities[mac])
        return new_entities

    initial_macs = set(coordinator.data.keys()) | set(known_entities.keys())
    entities = _build_entities(initial_macs)
    if entities:
        async_add_entities(entities)

    def _handle_coordinator_update() -> None:
        new_entities = _build_entities(set(coordinator.data.keys()))
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_handle_coordinator_update))
