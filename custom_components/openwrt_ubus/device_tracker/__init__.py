"""Device tracker platform for OpenWrt Ubus WiFi Presence."""

from __future__ import annotations

from custom_components.openwrt_ubus.data import OpenWrtUbusWifiPresenceConfigEntry
from custom_components.openwrt_ubus.device_tracker.manager import get_or_create_device_tracker_manager
from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass,
    entry: OpenWrtUbusWifiPresenceConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Register one router with the global WiFi device tracker manager."""
    manager = get_or_create_device_tracker_manager(hass)
    await manager.async_register_entry(entry, async_add_entities)
