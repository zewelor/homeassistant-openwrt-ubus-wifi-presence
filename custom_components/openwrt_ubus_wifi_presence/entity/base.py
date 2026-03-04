"""Base entity classes for OpenWrt Ubus WiFi Presence."""

from __future__ import annotations

from custom_components.openwrt_ubus.coordinator import OpenWrtUbusWifiPresenceCoordinator
from custom_components.openwrt_ubus.data import OpenWrtUbusWifiPresenceConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity


class OpenWrtUbusWifiPresenceEntity(CoordinatorEntity[OpenWrtUbusWifiPresenceCoordinator]):
    """Base entity bound to the OpenWrt WiFi presence coordinator."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OpenWrtUbusWifiPresenceCoordinator,
        entry: OpenWrtUbusWifiPresenceConfigEntry,
    ) -> None:
        """Initialize coordinator-backed base entity state."""
        super().__init__(coordinator)
        self._entry = entry
