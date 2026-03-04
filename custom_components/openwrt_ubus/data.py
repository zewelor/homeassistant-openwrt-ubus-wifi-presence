"""Data models for OpenWrt Ubus WiFi Presence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
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


class TrackerTargetType(StrEnum):
    """Kinds of tracker entities exposed by this integration."""

    ALIAS = "alias"
    MAC = "mac"


class TrackerTargetSource(StrEnum):
    """Source that made a tracker eligible for tracking."""

    ALIAS = "alias"
    KNOWN = "known"
    ALL = "all"


@dataclass(slots=True, frozen=True)
class TrackerTarget:
    """Represents one tracker entity that should exist in Home Assistant."""

    entity_key: str
    tracker_type: TrackerTargetType
    source: TrackerTargetSource
    display_name: str
    mac: str | None


@dataclass(slots=True)
class OpenWrtUbusWifiPresenceRuntimeData:
    """Objects stored as config entry runtime data."""

    client: OpenWrtUbusClient
    coordinator: OpenWrtUbusWifiPresenceCoordinator


type OpenWrtUbusWifiPresenceConfigEntry = ConfigEntry[OpenWrtUbusWifiPresenceRuntimeData]
