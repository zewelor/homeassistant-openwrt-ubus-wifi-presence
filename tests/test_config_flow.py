from __future__ import annotations

from logging import ERROR
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
import yaml

from custom_components.openwrt_ubus.api import (
    OpenWrtUbusAuthenticationError,
    OpenWrtUbusClientError,
    OpenWrtUbusCommunicationError,
    OpenWrtUbusNoWifiAccessPointError,
)
from custom_components.openwrt_ubus.config_flow_handler.handler import (
    _normalize_alias_mapping_ui,
    _validate_alias_mapping_ui,
    _validate_connection,
)
from custom_components.openwrt_ubus.const import (
    CONF_ALIAS_MAPPING_FILE,
    CONF_ALIAS_MAPPING_UI,
    CONF_ENDPOINT,
    CONF_IP_ADDRESS,
    CONF_MAPPING_SOURCE,
    CONF_TRACKING_MODE,
    CONF_USE_HTTPS,
    DOMAIN,
    LOGGER,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.data_entry_flow import FlowResultType

ROUTER_ID = "11:22:33:44:55:66"
LEGACY_SCAN_INTERVAL = "scan_interval"

FLOW_ERROR_CASES = (
    pytest.param(OpenWrtUbusAuthenticationError, "invalid_auth", False, id="authentication"),
    pytest.param(OpenWrtUbusNoWifiAccessPointError, "no_wifi_access_point", False, id="no-wifi-access-point"),
    pytest.param(OpenWrtUbusCommunicationError, "cannot_connect", False, id="communication"),
    pytest.param(OpenWrtUbusClientError, "unknown", True, id="unexpected-client"),
)


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
        )
    }


def _unexpected_log_records(caplog) -> list:
    """Return unexpected config-flow log records."""
    return [
        record
        for record in caplog.records
        if record.name == LOGGER.name and record.levelno >= ERROR and "while validating" in record.message
    ]


async def test_user_flow_shows_form_without_scan_interval(hass) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    schema_keys = {schema_key.schema for schema_key in result["data_schema"].schema}
    assert LEGACY_SCAN_INTERVAL not in schema_keys


async def test_user_flow_creates_entry(hass) -> None:
    with (
        patch(
            "custom_components.openwrt_ubus.config_flow_handler.handler._validate_connection",
            new=AsyncMock(return_value=ROUTER_ID),
        ),
        patch("custom_components.openwrt_ubus.async_setup_entry", new=AsyncMock(return_value=True)),
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
    assert LEGACY_SCAN_INTERVAL not in result["options"]


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

    with (
        patch(
            "custom_components.openwrt_ubus.config_flow_handler.handler._validate_connection",
            new=validate_connection,
        ),
        patch("custom_components.openwrt_ubus.async_setup_entry", new=AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data=user_input,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_ALIAS_MAPPING_UI: "invalid_alias_mapping_ui"}
    validate_connection.assert_not_awaited()


@pytest.mark.parametrize(("error_type", "error_key", "logs_exception"), FLOW_ERROR_CASES)
async def test_user_flow_maps_errors_and_recovers(
    hass,
    caplog,
    error_type: type[OpenWrtUbusClientError],
    error_key: str,
    logs_exception: bool,
) -> None:
    caplog.set_level(ERROR, logger=LOGGER.name)
    flow = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    validate_connection = AsyncMock(side_effect=[error_type("test failure"), ROUTER_ID])

    with (
        patch(
            "custom_components.openwrt_ubus.config_flow_handler.handler._validate_connection",
            new=validate_connection,
        ),
        patch("custom_components.openwrt_ubus.async_setup_entry", new=AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.flow.async_configure(flow["flow_id"], user_input=_user_input())
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": error_key}

        result = await hass.config_entries.flow.async_configure(flow["flow_id"], user_input=_user_input())

    assert result["type"] is FlowResultType.CREATE_ENTRY
    records = _unexpected_log_records(caplog)
    assert bool(records) is logs_exception
    if records:
        assert records[0].exc_info is not None


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


@pytest.mark.parametrize(("error_type", "error_key", "logs_exception"), FLOW_ERROR_CASES)
async def test_reauth_maps_errors_and_recovers(
    hass,
    caplog,
    error_type: type[OpenWrtUbusClientError],
    error_key: str,
    logs_exception: bool,
) -> None:
    caplog.set_level(ERROR, logger=LOGGER.name)
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ROUTER_ID, data=_connection_data(), options=_options())
    entry.add_to_hass(hass)
    flow = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": entry.entry_id},
        data=entry.data,
    )
    validate_connection = AsyncMock(side_effect=[error_type("test failure"), ROUTER_ID])
    credentials = {CONF_USERNAME: "new_user", CONF_PASSWORD: "new_pass"}

    with (
        patch(
            "custom_components.openwrt_ubus.config_flow_handler.handler._validate_connection",
            new=validate_connection,
        ),
        patch.object(hass.config_entries, "async_schedule_reload"),
    ):
        result = await hass.config_entries.flow.async_configure(flow["flow_id"], user_input=credentials)
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": error_key}

        result = await hass.config_entries.flow.async_configure(flow["flow_id"], user_input=credentials)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    records = _unexpected_log_records(caplog)
    assert bool(records) is logs_exception
    if records:
        assert records[0].exc_info is not None


async def test_reauth_rejects_connection_to_a_different_router(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ROUTER_ID, data=_connection_data(), options=_options())
    entry.add_to_hass(hass)
    flow = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": entry.entry_id},
        data=entry.data,
    )

    with patch(
        "custom_components.openwrt_ubus.config_flow_handler.handler._validate_connection",
        new=AsyncMock(return_value="AA:BB:CC:DD:EE:FF"),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            user_input={CONF_USERNAME: "new_user", CONF_PASSWORD: "new_pass"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert entry.data[CONF_USERNAME] == "root"


def _reconfigure_input() -> dict[str, object]:
    """Return connection data submitted through reconfigure."""
    return {
        CONF_HOST: "ap-renamed.example.com",
        CONF_IP_ADDRESS: "192.0.2.2",
        CONF_USE_HTTPS: True,
        CONF_PORT: 443,
        CONF_VERIFY_SSL: True,
        CONF_ENDPOINT: "ubus",
        CONF_USERNAME: "root2",
        CONF_PASSWORD: "",
    }


@pytest.mark.parametrize(
    ("submitted_password", "expected_password"),
    [("", "secret"), ("new_secret", "new_secret")],
)
async def test_reconfigure_updates_connection_and_keeps_router_identity(
    hass,
    submitted_password: str,
    expected_password: str,
) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ROUTER_ID, data=_connection_data(), options=_options())
    entry.add_to_hass(hass)

    flow = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reconfigure", "entry_id": entry.entry_id},
        data=None,
    )
    assert flow["type"] is FlowResultType.FORM
    assert flow["step_id"] == "reconfigure"

    reconfigure_input = _reconfigure_input()
    reconfigure_input[CONF_PASSWORD] = submitted_password

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
    assert entry.data[CONF_PASSWORD] == expected_password
    assert entry.title == "OpenWrt Ubus WiFi Presence (ap-renamed.example.com)"
    schedule_reload.assert_called_once_with(entry.entry_id)


@pytest.mark.parametrize(("error_type", "error_key", "logs_exception"), FLOW_ERROR_CASES)
async def test_reconfigure_maps_errors_and_recovers(
    hass,
    caplog,
    error_type: type[OpenWrtUbusClientError],
    error_key: str,
    logs_exception: bool,
) -> None:
    caplog.set_level(ERROR, logger=LOGGER.name)
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ROUTER_ID, data=_connection_data(), options=_options())
    entry.add_to_hass(hass)
    flow = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reconfigure", "entry_id": entry.entry_id},
        data=None,
    )
    validate_connection = AsyncMock(side_effect=[error_type("test failure"), ROUTER_ID])

    with (
        patch(
            "custom_components.openwrt_ubus.config_flow_handler.handler._validate_connection",
            new=validate_connection,
        ),
        patch.object(hass.config_entries, "async_schedule_reload"),
    ):
        result = await hass.config_entries.flow.async_configure(flow["flow_id"], user_input=_reconfigure_input())
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": error_key}

        result = await hass.config_entries.flow.async_configure(flow["flow_id"], user_input=_reconfigure_input())

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    records = _unexpected_log_records(caplog)
    assert bool(records) is logs_exception
    if records:
        assert records[0].exc_info is not None


async def test_reconfigure_rejects_connection_to_a_different_router(hass) -> None:
    """Test that a changed endpoint cannot silently replace entry identity."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ROUTER_ID, data=_connection_data(), options=_options())
    entry.add_to_hass(hass)
    flow = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reconfigure", "entry_id": entry.entry_id},
        data=None,
    )

    with patch(
        "custom_components.openwrt_ubus.config_flow_handler.handler._validate_connection",
        new=AsyncMock(return_value="AA:BB:CC:DD:EE:FF"),
    ):
        result = await hass.config_entries.flow.async_configure(flow["flow_id"], user_input=_reconfigure_input())

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert entry.data[CONF_HOST] == "ap-livingroom.example.com"


async def test_options_flow_rejects_invalid_alias_and_removes_legacy_interval(hass) -> None:
    options = {**_options(), LEGACY_SCAN_INTERVAL: 60}
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ROUTER_ID, data=_connection_data(), options=options)
    entry.add_to_hass(hass)

    flow = await hass.config_entries.options.async_init(entry.entry_id)
    assert flow["type"] is FlowResultType.FORM
    assert flow["step_id"] == "init"

    schema_keys = {schema_key.schema for schema_key in flow["data_schema"].schema}
    assert CONF_HOST not in schema_keys
    assert CONF_TRACKING_MODE in schema_keys
    assert LEGACY_SCAN_INTERVAL not in schema_keys

    result = await hass.config_entries.options.async_configure(
        flow["flow_id"],
        user_input={CONF_ALIAS_MAPPING_UI: "- not-a-mapping"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_ALIAS_MAPPING_UI: "invalid_alias_mapping_ui"}

    with patch.object(hass.config_entries, "async_schedule_reload") as schedule_reload:
        result = await hass.config_entries.options.async_configure(
            flow["flow_id"],
            user_input={
                CONF_TRACKING_MODE: "all",
                CONF_ALIAS_MAPPING_FILE: "custom_aliases.yaml",
                CONF_ALIAS_MAPPING_UI: "living_room_sensor: 11:22:33:44:55:66",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated_entry is not None
    assert updated_entry.options[CONF_TRACKING_MODE] == "all"
    assert LEGACY_SCAN_INTERVAL not in updated_entry.options
    assert CONF_TRACKING_MODE not in updated_entry.data
    schedule_reload.assert_called_once_with(entry.entry_id)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param(None, "", id="none"),
        pytest.param(42, "", id="non-string"),
        pytest.param("   ", "", id="blank"),
        pytest.param(" null ", "", id="yaml-null"),
        pytest.param(
            "  living_room_sensor: 11:22:33:44:55:66  ",
            "living_room_sensor: 11:22:33:44:55:66",
            id="valid-normalized",
        ),
    ],
)
def test_alias_mapping_validation_accepts_supported_values(value: object, expected: str) -> None:
    assert _normalize_alias_mapping_ui(value) == (value.strip() if isinstance(value, str) else "")
    assert _validate_alias_mapping_ui(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("[", id="invalid-yaml"),
        pytest.param("- item", id="non-mapping"),
        pytest.param("1: 11:22:33:44:55:66", id="non-string-alias"),
        pytest.param("' ': 11:22:33:44:55:66", id="empty-alias"),
        pytest.param(
            "'Living Room': 11:22:33:44:55:66\n'living-room': AA:BB:CC:DD:EE:FF",
            id="slug-collision",
        ),
        pytest.param("living_room_sensor: 123", id="non-string-mac"),
        pytest.param("living_room_sensor: not-a-mac", id="invalid-mac"),
    ],
)
def test_alias_mapping_validation_rejects_invalid_values(value: str) -> None:
    with pytest.raises((TypeError, ValueError, yaml.YAMLError)):
        _validate_alias_mapping_ui(value)


def test_alias_mapping_validation_rejects_empty_slug() -> None:
    with (
        patch("custom_components.openwrt_ubus.config_flow_handler.handler.slugify", return_value=""),
        pytest.raises(ValueError, match="Alias slug cannot be empty"),
    ):
        _validate_alias_mapping_ui("living_room_sensor: 11:22:33:44:55:66")


async def test_validate_connection_closes_client_after_success(hass) -> None:
    with (
        patch("custom_components.openwrt_ubus.config_flow_handler.handler.async_get_clientsession"),
        patch(
            "custom_components.openwrt_ubus.config_flow_handler.handler.OpenWrtUbusClient", autospec=True
        ) as client_class,
    ):
        client = client_class.return_value
        client.get_router_identifier.return_value = ROUTER_ID

        result = await _validate_connection(hass, _connection_data())

    assert result == ROUTER_ID
    client.connect.assert_awaited_once_with()
    client.get_router_identifier.assert_awaited_once_with()
    client.close.assert_awaited_once_with()


async def test_validate_connection_closes_client_after_error(hass) -> None:
    with (
        patch("custom_components.openwrt_ubus.config_flow_handler.handler.async_get_clientsession"),
        patch(
            "custom_components.openwrt_ubus.config_flow_handler.handler.OpenWrtUbusClient", autospec=True
        ) as client_class,
    ):
        client = client_class.return_value
        client.connect.side_effect = OpenWrtUbusCommunicationError("test failure")

        with pytest.raises(OpenWrtUbusCommunicationError):
            await _validate_connection(hass, _connection_data())

    client.close.assert_awaited_once_with()
