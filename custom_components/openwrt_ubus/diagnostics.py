"""Diagnostics support for OpenWrt Ubus WiFi Presence."""

from __future__ import annotations

from dataclasses import asdict

from homeassistant.components.diagnostics import async_redact_data

from .const import SENSITIVE_CONFIG_KEYS
from .data import OpenWrtUbusWifiPresenceConfigEntry


async def async_get_config_entry_diagnostics(hass, entry: OpenWrtUbusWifiPresenceConfigEntry) -> dict:
    """Return diagnostics for a config entry."""
    del hass

    coordinator = entry.runtime_data.coordinator
    devices = {mac: asdict(device) for mac, device in entry.runtime_data.coordinator.data.items()}
    tracker_targets = {
        key: {
            "type": target.tracker_type.value,
            "source": target.source.value,
            "name": target.display_name,
            "mac": target.mac,
        }
        for key, target in coordinator.tracker_targets.items()
    }

    return {
        "entry": async_redact_data(entry.as_dict(), SENSITIVE_CONFIG_KEYS),
        "devices": devices,
        "tracking_mode": coordinator.tracking_mode,
        "alias_mapping_file": coordinator.alias_mapping_file,
        "tracker_targets": tracker_targets,
    }
