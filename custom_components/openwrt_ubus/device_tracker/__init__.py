"""Device tracker platform for OpenWrt Ubus WiFi Presence."""

from __future__ import annotations

from custom_components.openwrt_ubus.data import OpenWrtUbusWifiPresenceConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass,
    entry: OpenWrtUbusWifiPresenceConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Register one router with the global WiFi device tracker manager."""
    del hass
    manager = entry.runtime_data.device_tracker_manager
    await manager.async_register_entry(entry, async_add_entities)
