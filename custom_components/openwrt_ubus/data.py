"""Data models for OpenWrt Ubus WiFi Presence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .api import OpenWrtUbusClient
    from .binary_sensor import OpenWrtUbusSsidPresenceManager
    from .coordinator import OpenWrtUbusWifiPresenceCoordinator
    from .device_tracker.manager import OpenWrtUbusWifiPresenceDeviceTrackerManager


@dataclass(slots=True)
class WifiPresenceDevice:
    """Represents one currently associated WiFi station reported by ubus."""

    mac: str
    ap_device: str
    ssid: str | None
    inactive_ms: int | None = None
    signal_dbm: int | None = None


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
    device_tracker_manager: OpenWrtUbusWifiPresenceDeviceTrackerManager
    ssid_presence_manager: OpenWrtUbusSsidPresenceManager


type OpenWrtUbusWifiPresenceConfigEntry = ConfigEntry[OpenWrtUbusWifiPresenceRuntimeData]
