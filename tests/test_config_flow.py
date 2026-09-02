from __future__ import annotations

from unittest.mock import AsyncMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openwrt_ubus.api import OpenWrtUbusNoWifiAccessPointError
from custom_components.openwrt_ubus.const import (
    CONF_ALIAS_MAPPING_FILE,
    CONF_ALIAS_MAPPING_UI,
    CONF_ENDPOINT,
    CONF_IP_ADDRESS,
    CONF_MAPPING_SOURCE,
    CONF_SCAN_INTERVAL,
    CONF_TRACKING_MODE,
    CONF_USE_HTTPS,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.data_entry_flow import FlowResultType

ROUTER_ID = "11:22:33:44:55:66"


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
        CONF_MAPPING_SOURCE: "hybrid",
        CONF_ALIAS_MAPPING_UI: "",
        CONF_SCAN_INTERVAL: 30,
    }


def _connection_data() -> dict[str, object]:
    """Return the persistent connection part of a config entry."""
    user_input = _user_input()
    return {
        key: user_input[key]
        for key in (
            CONF_HOST,
            CONF_IP_ADDRESS,
            CONF_USE_HTTPS,
            CONF_PORT,
            CONF_VERIFY_SSL,
            CONF_ENDPOINT,
            CONF_USERNAME,
            CONF_PASSWORD,
        )
    }


def _options() -> dict[str, object]:
    """Return the behavioral options of a config entry."""
    user_input = _user_input()
    return {
        key: user_input[key]
        for key in (
            CONF_TRACKING_MODE,
            CONF_ALIAS_MAPPING_FILE,
            CONF_MAPPING_SOURCE,
            CONF_ALIAS_MAPPING_UI,
            CONF_SCAN_INTERVAL,
        )
    }


async def test_user_flow_creates_entry(hass) -> None:
    with patch(
        "custom_components.openwrt_ubus.config_flow_handler.handler._validate_connection",
        new=AsyncMock(return_value=ROUTER_ID),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data=_user_input(),
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OpenWrt Ubus WiFi Presence (ap-livingroom.example.com)"
    assert result["result"].unique_id == ROUTER_ID
    assert result["result"].version == 3
    assert CONF_TRACKING_MODE not in result["data"]
    assert result["options"][CONF_TRACKING_MODE] == "known_or_alias"
    assert result["options"][CONF_MAPPING_SOURCE] == "hybrid"


async def test_user_flow_aborts_when_router_already_configured(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ROUTER_ID, data=_connection_data(), options=_options())
    entry.add_to_hass(hass)

    with patch(
        "custom_components.openwrt_ubus.config_flow_handler.handler._validate_connection",
        new=AsyncMock(return_value=ROUTER_ID),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data=_user_input(),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_rejects_invalid_alias_mapping_before_connecting(hass) -> None:
    user_input = _user_input()
    user_input[CONF_ALIAS_MAPPING_UI] = "- not-a-mapping"
    validate_connection = AsyncMock(return_value=ROUTER_ID)

    with patch(
        "custom_components.openwrt_ubus.config_flow_handler.handler._validate_connection",
        new=validate_connection,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data=user_input,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_ALIAS_MAPPING_UI: "invalid_alias_mapping_ui"}
    validate_connection.assert_not_awaited()


async def test_user_flow_reports_missing_wifi_access_point(hass) -> None:
    """Test setup distinguishes missing local WiFi APs from network failures."""
    with patch(
        "custom_components.openwrt_ubus.config_flow_handler.handler._validate_connection",
        new=AsyncMock(side_effect=OpenWrtUbusNoWifiAccessPointError),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data=_user_input(),
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "no_wifi_access_point"}


async def test_reauth_updates_credentials(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ROUTER_ID, data=_connection_data(), options=_options())
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
            new=AsyncMock(return_value=ROUTER_ID),
        ),
        patch.object(hass.config_entries, "async_schedule_reload") as schedule_reload,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            user_input={CONF_USERNAME: "new_user", CONF_PASSWORD: "new_pass"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_USERNAME] == "new_user"
    assert entry.data[CONF_PASSWORD] == "new_pass"
    schedule_reload.assert_called_once_with(entry.entry_id)


async def test_reconfigure_updates_connection_and_keeps_router_identity(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ROUTER_ID, data=_connection_data(), options=_options())
    entry.add_to_hass(hass)

    flow = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reconfigure", "entry_id": entry.entry_id},
        data=None,
    )
    assert flow["type"] is FlowResultType.FORM
    assert flow["step_id"] == "reconfigure"

    reconfigure_input = {
        CONF_HOST: "ap-renamed.example.com",
        CONF_IP_ADDRESS: "192.168.1.2",
        CONF_USE_HTTPS: True,
        CONF_PORT: 443,
        CONF_VERIFY_SSL: True,
        CONF_ENDPOINT: "ubus",
        CONF_USERNAME: "root2",
    }

    with (
        patch(
            "custom_components.openwrt_ubus.config_flow_handler.handler._validate_connection",
            new=AsyncMock(return_value=ROUTER_ID),
        ),
        patch.object(hass.config_entries, "async_schedule_reload") as schedule_reload,
    ):
        result = await hass.config_entries.flow.async_configure(flow["flow_id"], user_input=reconfigure_input)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "ap-renamed.example.com"
    assert entry.unique_id == ROUTER_ID
    assert entry.data[CONF_USE_HTTPS] is True
    assert entry.data[CONF_VERIFY_SSL] is True
    assert entry.data[CONF_USERNAME] == "root2"
    assert entry.data[CONF_PASSWORD] == "secret"
    assert entry.title == "OpenWrt Ubus WiFi Presence (ap-renamed.example.com)"
    schedule_reload.assert_called_once_with(entry.entry_id)


async def test_reconfigure_rejects_connection_to_a_different_router(hass) -> None:
    """Test that a changed endpoint cannot silently replace entry identity."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ROUTER_ID, data=_connection_data(), options=_options())
    entry.add_to_hass(hass)
    flow = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reconfigure", "entry_id": entry.entry_id},
        data=None,
    )
    changed_input = _connection_data()
    changed_input[CONF_HOST] = "router-kitchen.example.com"

    with patch(
        "custom_components.openwrt_ubus.config_flow_handler.handler._validate_connection",
        new=AsyncMock(return_value="AA:BB:CC:DD:EE:FF"),
    ):
        result = await hass.config_entries.flow.async_configure(flow["flow_id"], user_input=changed_input)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert entry.data[CONF_HOST] == "ap-livingroom.example.com"


async def test_options_flow_updates_only_options(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ROUTER_ID, data=_connection_data(), options=_options())
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
        CONF_SCAN_INTERVAL: 60,
    }

    with patch.object(hass.config_entries, "async_schedule_reload") as schedule_reload:
        result = await hass.config_entries.options.async_configure(flow["flow_id"], user_input=options_input)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated_entry is not None
    assert updated_entry.options[CONF_TRACKING_MODE] == "all"
    assert updated_entry.options[CONF_SCAN_INTERVAL] == 60
    assert CONF_TRACKING_MODE not in updated_entry.data
    schedule_reload.assert_called_once_with(entry.entry_id)
