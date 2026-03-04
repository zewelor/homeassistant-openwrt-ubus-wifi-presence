"""Base entity classes for OpenWrt Ubus WiFi Presence."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..coordinator import OpenWrtUbusWifiPresenceCoordinator
from ..data import OpenWrtUbusWifiPresenceConfigEntry


class OpenWrtUbusWifiPresenceEntity(CoordinatorEntity[OpenWrtUbusWifiPresenceCoordinator]):
    """Base entity bound to the OpenWrt WiFi presence coordinator."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OpenWrtUbusWifiPresenceCoordinator,
        entry: OpenWrtUbusWifiPresenceConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
