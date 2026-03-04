"""Data models for OpenWrt Ubus WiFi Presence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .api import OpenWrtUbusClient
    from .coordinator import OpenWrtUbusWifiPresenceCoordinator


@dataclass(slots=True)
class WifiPresenceDevice:
    """Represents one WiFi station tracked through ubus."""

    mac: str
    hostname: str | None
    ip_address: str | None
    ap_device: str
    ssid: str | None
    connected: bool = True


@dataclass(slots=True)
class OpenWrtUbusWifiPresenceRuntimeData:
    """Objects stored as config entry runtime data."""

    client: OpenWrtUbusClient
    coordinator: OpenWrtUbusWifiPresenceCoordinator


type OpenWrtUbusWifiPresenceConfigEntry = ConfigEntry[OpenWrtUbusWifiPresenceRuntimeData]
