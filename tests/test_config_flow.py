from __future__ import annotations

from unittest.mock import AsyncMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openwrt_ubus.const import (
    CONF_ALIAS_MAPPING_FILE,
    CONF_ENDPOINT,
    CONF_IP_ADDRESS,
    CONF_SCAN_INTERVAL,
    CONF_TRACKING_MODE,
    CONF_USE_HTTPS,
    CONF_WIRELESS_SOFTWARE,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.data_entry_flow import FlowResultType


def _user_input() -> dict[str, object]:
    return {
        CONF_HOST: "ap-livingroom.example.com",
        CONF_IP_ADDRESS: "",
        CONF_USE_HTTPS: False,
        CONF_PORT: None,
        CONF_VERIFY_SSL: False,
        CONF_ENDPOINT: "ubus",
        CONF_USERNAME: "root",
        CONF_PASSWORD: "secret",
        CONF_TRACKING_MODE: "known_or_alias",
        CONF_ALIAS_MAPPING_FILE: "openwrt_ubus_aliases.yaml",
        CONF_WIRELESS_SOFTWARE: "iwinfo",
        CONF_SCAN_INTERVAL: 30,
    }


async def test_user_flow_creates_entry(hass) -> None:
    with patch(
        "custom_components.openwrt_ubus.config_flow_handler.handler._validate_connection",
        new=AsyncMock(return_value=None),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data=_user_input(),
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OpenWrt Ubus WiFi Presence (ap-livingroom.example.com)"


async def test_user_flow_aborts_when_host_already_configured(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="ap-livingroom.example.com", data=_user_input())
    entry.add_to_hass(hass)

    with patch(
        "custom_components.openwrt_ubus.config_flow_handler.handler._validate_connection",
        new=AsyncMock(return_value=None),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data=_user_input(),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_updates_credentials(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="ap-livingroom.example.com", data=_user_input())
    entry.add_to_hass(hass)

    flow = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": entry.entry_id},
        data=entry.data,
    )
    assert flow["type"] is FlowResultType.FORM
    assert flow["step_id"] == "reauth_confirm"

    with (
        patch(
            "custom_components.openwrt_ubus.config_flow_handler.handler._validate_connection",
            new=AsyncMock(return_value=None),
        ),
        patch.object(hass.config_entries, "async_reload", AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            user_input={CONF_USERNAME: "new_user", CONF_PASSWORD: "new_pass"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_USERNAME] == "new_user"
    assert entry.data[CONF_PASSWORD] == "new_pass"


async def test_reconfigure_updates_connection_but_keeps_host(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="ap-livingroom.example.com", data=_user_input())
    entry.add_to_hass(hass)

    flow = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reconfigure", "entry_id": entry.entry_id},
        data=None,
    )
    assert flow["type"] is FlowResultType.FORM
    assert flow["step_id"] == "reconfigure"

    reconfigure_input = {
        CONF_IP_ADDRESS: "192.168.1.2",
        CONF_USE_HTTPS: True,
        CONF_PORT: 443,
        CONF_VERIFY_SSL: True,
        CONF_ENDPOINT: "ubus",
        CONF_USERNAME: "root2",
        CONF_PASSWORD: "pass2",
    }

    with (
        patch(
            "custom_components.openwrt_ubus.config_flow_handler.handler._validate_connection",
            new=AsyncMock(return_value=None),
        ),
        patch.object(hass.config_entries, "async_reload", AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.flow.async_configure(flow["flow_id"], user_input=reconfigure_input)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "ap-livingroom.example.com"
    assert entry.data[CONF_USE_HTTPS] is True
    assert entry.data[CONF_VERIFY_SSL] is True
    assert entry.data[CONF_USERNAME] == "root2"


async def test_options_flow_updates_only_options(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="ap-livingroom.example.com", data=_user_input())
    entry.add_to_hass(hass)

    flow = await hass.config_entries.options.async_init(entry.entry_id)
    assert flow["type"] is FlowResultType.FORM
    assert flow["step_id"] == "init"

    schema_keys = {schema_key.schema for schema_key in flow["data_schema"].schema}
    assert CONF_HOST not in schema_keys
    assert CONF_TRACKING_MODE in schema_keys
    assert CONF_SCAN_INTERVAL in schema_keys

    options_input = {
        CONF_TRACKING_MODE: "all",
        CONF_ALIAS_MAPPING_FILE: "custom_aliases.yaml",
        CONF_WIRELESS_SOFTWARE: "hostapd",
        CONF_SCAN_INTERVAL: 60,
    }

    result = await hass.config_entries.options.async_configure(flow["flow_id"], user_input=options_input)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated_entry is not None
    assert updated_entry.options[CONF_TRACKING_MODE] == "all"
    assert updated_entry.options[CONF_SCAN_INTERVAL] == 60
    assert updated_entry.data[CONF_TRACKING_MODE] == "known_or_alias"
