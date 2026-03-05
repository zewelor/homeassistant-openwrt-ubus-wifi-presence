"""Diagnostics support for OpenWrt Ubus WiFi Presence."""

from __future__ import annotations

from dataclasses import asdict

from homeassistant.components.diagnostics import async_redact_data

from .const import SENSITIVE_DIAGNOSTIC_KEYS
from .data import OpenWrtUbusWifiPresenceConfigEntry


async def async_get_config_entry_diagnostics(hass, entry: OpenWrtUbusWifiPresenceConfigEntry) -> dict:
    """Return diagnostics for a config entry."""
    del hass

    coordinator = entry.runtime_data.coordinator
    devices = [asdict(device) for device in coordinator.data.values()]
    tracker_targets = {
        key: {
            "type": target.tracker_type.value,
            "source": target.source.value,
            "name": target.display_name,
            "mac": target.mac,
        }
        for key, target in coordinator.tracker_targets.items()
    }

    diagnostics = {
        "entry": entry.as_dict(),
        "devices": devices,
        "tracking_mode": getattr(coordinator, "tracking_mode", "known_or_alias"),
        "mapping_source": getattr(coordinator, "mapping_source", "hybrid"),
        "alias_mapping_file": getattr(coordinator, "alias_mapping_file", ""),
        "alias_mapping_summary": getattr(coordinator, "alias_mapping_summary", {}),
        "tracker_targets": tracker_targets,
    }
    return async_redact_data(diagnostics, SENSITIVE_DIAGNOSTIC_KEYS)
