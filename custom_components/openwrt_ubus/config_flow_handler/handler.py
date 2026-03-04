"""Config flow for OpenWrt Ubus WiFi Presence."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from custom_components.openwrt_ubus.api import (
    OpenWrtUbusAuthenticationError,
    OpenWrtUbusClient,
    OpenWrtUbusClientError,
    OpenWrtUbusCommunicationError,
)
from custom_components.openwrt_ubus.const import (
    CONF_ALIAS_MAPPING_FILE,
    CONF_DHCP_SOFTWARE,
    CONF_ENDPOINT,
    CONF_IP_ADDRESS,
    CONF_SCAN_INTERVAL,
    CONF_TRACKING_MODE,
    CONF_USE_HTTPS,
    CONF_WIRELESS_SOFTWARE,
    DEFAULT_ALIAS_MAPPING_FILE,
    DEFAULT_DHCP_SOFTWARE,
    DEFAULT_ENDPOINT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TRACKING_MODE,
    DEFAULT_USE_HTTPS,
    DEFAULT_WIRELESS_SOFTWARE,
    DHCP_SOFTWARES,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    TRACKING_MODES,
    WIRELESS_SOFTWARES,
    build_ubus_url,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession


def _build_user_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Build user/options form schema."""
    values = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=values.get(CONF_HOST, "")): str,
            vol.Optional(CONF_IP_ADDRESS, default=values.get(CONF_IP_ADDRESS, "")): str,
            vol.Optional(CONF_USE_HTTPS, default=values.get(CONF_USE_HTTPS, DEFAULT_USE_HTTPS)): bool,
            vol.Optional(CONF_PORT, default=values.get(CONF_PORT)): vol.Any(
                None, vol.All(vol.Coerce(int), vol.Range(1, 65535))
            ),
            vol.Optional(CONF_VERIFY_SSL, default=values.get(CONF_VERIFY_SSL, False)): bool,
            vol.Optional(CONF_ENDPOINT, default=values.get(CONF_ENDPOINT, DEFAULT_ENDPOINT)): str,
            vol.Required(CONF_USERNAME, default=values.get(CONF_USERNAME, "")): str,
            vol.Required(CONF_PASSWORD, default=values.get(CONF_PASSWORD, "")): str,
            vol.Optional(
                CONF_TRACKING_MODE,
                default=values.get(CONF_TRACKING_MODE, DEFAULT_TRACKING_MODE),
            ): vol.In(TRACKING_MODES),
            vol.Optional(
                CONF_ALIAS_MAPPING_FILE,
                default=values.get(CONF_ALIAS_MAPPING_FILE, DEFAULT_ALIAS_MAPPING_FILE),
            ): str,
            vol.Optional(
                CONF_WIRELESS_SOFTWARE,
                default=values.get(CONF_WIRELESS_SOFTWARE, DEFAULT_WIRELESS_SOFTWARE),
            ): vol.In(WIRELESS_SOFTWARES),
            vol.Optional(
                CONF_DHCP_SOFTWARE,
                default=values.get(CONF_DHCP_SOFTWARE, DEFAULT_DHCP_SOFTWARE),
            ): vol.In(DHCP_SOFTWARES),
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=values.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)),
        }
    )


async def _validate_connection(hass, data: dict[str, Any]) -> None:
    """Validate OpenWrt credentials and endpoint."""
    url = build_ubus_url(
        host=data[CONF_HOST],
        use_https=data.get(CONF_USE_HTTPS, DEFAULT_USE_HTTPS),
        ip_address=data.get(CONF_IP_ADDRESS) or None,
        port=data.get(CONF_PORT),
        endpoint=data.get(CONF_ENDPOINT, DEFAULT_ENDPOINT),
    )

    client = OpenWrtUbusClient(
        session=async_get_clientsession(hass, verify_ssl=data.get(CONF_VERIFY_SSL, False)),
        url=url,
        host=data[CONF_HOST],
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        verify_ssl=data.get(CONF_VERIFY_SSL, False),
    )

    await client.connect()
    await client.close()


class OpenWrtUbusWifiPresenceConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle config flow for OpenWrt Ubus WiFi Presence."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        """Return options flow handler."""
        return OpenWrtUbusWifiPresenceOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle initial setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await _validate_connection(self.hass, user_input)
            except OpenWrtUbusAuthenticationError:
                errors["base"] = "invalid_auth"
            except OpenWrtUbusCommunicationError:
                errors["base"] = "cannot_connect"
            except OpenWrtUbusClientError:
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()
                title = f"OpenWrt Ubus WiFi Presence ({user_input[CONF_HOST]})"
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(step_id="user", data_schema=_build_user_schema(), errors=errors)


class OpenWrtUbusWifiPresenceOptionsFlow(OptionsFlow):
    """Handle options updates for OpenWrt Ubus WiFi Presence."""

    def __init__(self, config_entry) -> None:
        """Initialize options flow."""
        super().__init__()
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle options form."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await _validate_connection(self.hass, user_input)
            except OpenWrtUbusAuthenticationError:
                errors["base"] = "invalid_auth"
            except OpenWrtUbusCommunicationError:
                errors["base"] = "cannot_connect"
            except OpenWrtUbusClientError:
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(self._config_entry, data=user_input)
                await self.hass.config_entries.async_reload(self._config_entry.entry_id)
                return self.async_create_entry(title="", data={})

        current = dict(self._config_entry.data)
        return self.async_show_form(step_id="init", data_schema=_build_user_schema(current), errors=errors)
