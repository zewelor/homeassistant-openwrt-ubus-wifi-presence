"""Diagnostics support for OpenWrt Ubus WiFi Presence."""

from __future__ import annotations

from dataclasses import asdict

from homeassistant.components.diagnostics import async_redact_data

from .const import SENSITIVE_CONFIG_KEYS
from .data import OpenWrtUbusWifiPresenceConfigEntry


async def async_get_config_entry_diagnostics(hass, entry: OpenWrtUbusWifiPresenceConfigEntry) -> dict:
    """Return diagnostics for a config entry."""
    del hass

    devices = {mac: asdict(device) for mac, device in entry.runtime_data.coordinator.data.items()}

    return {
        "entry": async_redact_data(entry.as_dict(), SENSITIVE_CONFIG_KEYS),
        "devices": devices,
    }
