"""OpenWrt Ubus WiFi Presence integration."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .api import OpenWrtUbusClient
from .binary_sensor import OpenWrtUbusSsidPresenceManager
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
from .device_tracker.manager import OpenWrtUbusWifiPresenceDeviceTrackerManager

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up integration domain."""
    del hass, config
    return True


def _get_shared_managers(
    hass: HomeAssistant,
) -> tuple[OpenWrtUbusWifiPresenceDeviceTrackerManager, OpenWrtUbusSsidPresenceManager]:
    """Return managers already owned by another initialized config entry."""
    for configured_entry in hass.config_entries.async_entries(DOMAIN):
        runtime_data = getattr(configured_entry, "runtime_data", None)
        if isinstance(runtime_data, OpenWrtUbusWifiPresenceRuntimeData):
            return runtime_data.device_tracker_manager, runtime_data.ssid_presence_manager

    return OpenWrtUbusWifiPresenceDeviceTrackerManager(hass), OpenWrtUbusSsidPresenceManager(hass)


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
    device_tracker_manager, ssid_presence_manager = _get_shared_managers(hass)
    entry.runtime_data = OpenWrtUbusWifiPresenceRuntimeData(
        client=client,
        coordinator=coordinator,
        device_tracker_manager=device_tracker_manager,
        ssid_presence_manager=ssid_presence_manager,
    )
    first_refresh_complete = False
    try:
        await coordinator.async_config_entry_first_refresh()
        first_refresh_complete = True
    finally:
        if not first_refresh_complete:
            try:
                await client.close()
            finally:
                del entry.runtime_data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OpenWrtUbusWifiPresenceConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.client.close()
    return unload_ok
