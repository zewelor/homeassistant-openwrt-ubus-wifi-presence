"""OpenWrt Ubus WiFi Presence integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .api import OpenWrtUbusAuthenticationError, OpenWrtUbusClient, OpenWrtUbusCommunicationError
from .const import (
    CONF_ENDPOINT,
    CONF_IP_ADDRESS,
    CONF_USE_HTTPS,
    DEFAULT_ENDPOINT,
    DEFAULT_USE_HTTPS,
    DOMAIN,
    PLATFORMS,
    build_ubus_url,
)
from .coordinator import OpenWrtUbusWifiPresenceCoordinator
from .data import OpenWrtUbusWifiPresenceConfigEntry, OpenWrtUbusWifiPresenceRuntimeData

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def _async_cleanup_legacy_tracker_devices(
    hass: HomeAssistant,
    entry: OpenWrtUbusWifiPresenceConfigEntry,
) -> None:
    """Remove legacy per-client device entries from pre-ScannerEntity versions."""
    device_registry = dr.async_get(hass)
    for device_entry in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if not any(identifier[0] == DOMAIN for identifier in device_entry.identifiers):
            continue
        device_registry.async_remove_device(device_entry.id)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up integration domain."""
    del hass, config
    return True


async def async_setup_entry(hass: HomeAssistant, entry: OpenWrtUbusWifiPresenceConfigEntry) -> bool:
    """Set up OpenWrt Ubus WiFi Presence from config entry."""
    url = build_ubus_url(
        host=entry.data[CONF_HOST],
        use_https=entry.data.get(CONF_USE_HTTPS, DEFAULT_USE_HTTPS),
        ip_address=entry.data.get(CONF_IP_ADDRESS) or None,
        port=entry.data.get(CONF_PORT),
        endpoint=entry.data.get(CONF_ENDPOINT, DEFAULT_ENDPOINT),
    )

    client = OpenWrtUbusClient(
        session=async_get_clientsession(hass, verify_ssl=entry.data.get(CONF_VERIFY_SSL, False)),
        url=url,
        host=entry.data[CONF_HOST],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        verify_ssl=entry.data.get(CONF_VERIFY_SSL, False),
    )

    coordinator = OpenWrtUbusWifiPresenceCoordinator(hass=hass, entry=entry, client=client)

    try:
        await coordinator.async_config_entry_first_refresh()
    except OpenWrtUbusAuthenticationError as err:
        raise ConfigEntryAuthFailed("OpenWrt ubus authentication failed") from err
    except OpenWrtUbusCommunicationError as err:
        raise ConfigEntryNotReady("Cannot connect to OpenWrt ubus endpoint") from err

    await _async_cleanup_legacy_tracker_devices(hass, entry)
    entry.runtime_data = OpenWrtUbusWifiPresenceRuntimeData(client=client, coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OpenWrtUbusWifiPresenceConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.client.close()
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
