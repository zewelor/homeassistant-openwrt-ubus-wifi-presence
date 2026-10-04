"""Smoke tests for tracking-mode changes through Home Assistant options."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.openwrt_ubus.api import OpenWrtUbusClient, OpenWrtUbusCommunicationError
from custom_components.openwrt_ubus.const import CONF_ALIAS_MAPPING_UI, CONF_MAPPING_SOURCE, CONF_TRACKING_MODE, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, STATE_HOME, STATE_NOT_HOME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er

ALIAS_MAC = "11:22:33:44:55:66"
KNOWN_MAC = "AA:BB:CC:DD:EE:FF"
UNKNOWN_MAC = "22:33:44:55:66:77"


@pytest.fixture
def mock_wifi_clients() -> Iterator[AsyncMock]:
    """Mock only the OpenWrt Wi-Fi inventory and association API."""
    with (
        patch.object(
            OpenWrtUbusClient,
            "get_wifi_ssid_inventory",
            new=AsyncMock(return_value=({"wlan0": "MyNetwork"}, {"MyNetwork"}, True)),
        ),
        patch.object(OpenWrtUbusClient, "get_iwinfo_ap_devices", new=AsyncMock(return_value=["wlan0"])),
        patch.object(OpenWrtUbusClient, "get_iwinfo_assoclist", new=AsyncMock(return_value=[])) as clients,
    ):
        yield clients


@pytest.mark.integration
@pytest.mark.parametrize(
    ("alias_mapping", "observed_macs", "expected_alias_states"),
    [
        pytest.param(
            f"living_room_sensor: {ALIAS_MAC}",
            [ALIAS_MAC, KNOWN_MAC, UNKNOWN_MAC],
            {"device_tracker.living_room_sensor": STATE_HOME},
            id="alias-present",
        ),
        pytest.param(
            f"living_room_sensor: {ALIAS_MAC}",
            [KNOWN_MAC, UNKNOWN_MAC],
            {"device_tracker.living_room_sensor": STATE_NOT_HOME},
            id="alias-absent",
        ),
        pytest.param(
            "",
            [ALIAS_MAC, KNOWN_MAC, UNKNOWN_MAC],
            {},
            id="empty-alias-mapping",
        ),
    ],
)
async def test_aliases_only_mode_smoke(
    *,
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    alias_mapping: str,
    observed_macs: list[str],
    expected_alias_states: dict[str, str],
) -> None:
    """Switch to aliases only and back without losing registry identities."""
    source_entry = MockConfigEntry(domain="test", unique_id="known-device-source")
    source_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=source_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, KNOWN_MAC)},
        name="Kitchen Device",
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="02:00:00:00:00:01",
        version=3,
        data={CONF_HOST: "router-office.lan", CONF_USERNAME: "root", CONF_PASSWORD: "test-password"},
        options={
            CONF_TRACKING_MODE: "known_or_alias",
            CONF_MAPPING_SOURCE: "ui",
            CONF_ALIAS_MAPPING_UI: alias_mapping,
        },
    )
    entry.add_to_hass(hass)

    with (
        patch.object(
            OpenWrtUbusClient,
            "get_wifi_ssid_inventory",
            new=AsyncMock(return_value=({"wlan0": "MyNetwork"}, {"MyNetwork"}, True)),
        ),
        patch.object(OpenWrtUbusClient, "get_iwinfo_ap_devices", new=AsyncMock(return_value=["wlan0"])),
        patch.object(
            OpenWrtUbusClient,
            "get_iwinfo_assoclist",
            new=AsyncMock(return_value=[{"mac": mac, "authorized": True} for mac in observed_macs]),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED

        known_entity_id = entity_registry.async_get_entity_id("device_tracker", DOMAIN, f"mac_{KNOWN_MAC}")
        assert known_entity_id is not None
        known_registry_entry = entity_registry.async_get(known_entity_id)
        assert known_registry_entry is not None
        original_registry_ids = {
            registry_entry.entity_id: registry_entry.id
            for registry_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
            if registry_entry.domain == "device_tracker"
        }
        expected_known_states = {**expected_alias_states, known_entity_id: STATE_HOME}
        assert {
            state.entity_id: state.state for state in hass.states.async_all("device_tracker")
        } == expected_known_states

        flow = await hass.config_entries.options.async_init(entry.entry_id)
        assert flow["type"] is FlowResultType.FORM
        result = await hass.config_entries.options.async_configure(
            flow["flow_id"],
            user_input={**entry.options, CONF_TRACKING_MODE: "aliases_only"},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        assert entry.options[CONF_TRACKING_MODE] == "aliases_only"
        assert entity_registry.async_get(known_entity_id) is None
        assert hass.states.get(known_entity_id) is None
        assert {
            state.entity_id: state.state for state in hass.states.async_all("device_tracker")
        } == expected_alias_states

        flow = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            flow["flow_id"],
            user_input={**entry.options, CONF_TRACKING_MODE: "known_or_alias"},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        assert {
            state.entity_id: state.state for state in hass.states.async_all("device_tracker")
        } == expected_known_states

        restored_entry = entity_registry.async_get(known_entity_id)
        assert restored_entry is not None
        assert restored_entry.disabled_by is None
        assert restored_entry.hidden_by is None
        assert {
            registry_entry.entity_id: registry_entry.id
            for registry_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
            if registry_entry.domain == "device_tracker"
        } == original_registry_ids

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.integration
async def test_tracking_mode_cleanup_across_routers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_wifi_clients: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Keep offline and uncertain trackers; remove only globally excluded ones."""
    source_entry = MockConfigEntry(domain="test", unique_id="known-device-source")
    source_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=source_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, KNOWN_MAC)},
    )
    other_entity = entity_registry.async_get_or_create(
        "sensor", "test", "known-device-sensor", config_entry=source_entry, device_id=device.id
    )
    entries = []
    for host, mode in [("router-office.lan", "known_or_alias"), ("router-kitchen.lan", "all")]:
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id=host,
            version=3,
            data={CONF_HOST: host, CONF_USERNAME: "root", CONF_PASSWORD: "test-password"},
            options={CONF_TRACKING_MODE: mode, CONF_MAPPING_SOURCE: "ui", CONF_ALIAS_MAPPING_UI: ""},
        )
        entry.add_to_hass(hass)
        entries.append(entry)
    first, second = entries
    mock_wifi_clients.return_value = [{"mac": KNOWN_MAC, "authorized": True}]
    assert await hass.config_entries.async_setup(first.entry_id)
    await hass.async_block_till_done()
    assert all(entry.state is ConfigEntryState.LOADED for entry in entries)

    entity_id = entity_registry.async_get_entity_id("device_tracker", DOMAIN, f"mac_{KNOWN_MAC}")
    assert entity_id is not None
    original = entity_registry.async_update_entity(entity_id, name="Kitchen Device", icon="mdi:router-wireless")

    flow = await hass.config_entries.options.async_init(first.entry_id)
    await hass.config_entries.options.async_configure(
        flow["flow_id"], user_input={**first.options, CONF_TRACKING_MODE: "aliases_only"}
    )
    await hass.async_block_till_done()
    assert entity_registry.async_get(entity_id).id == original.id
    assert hass.states.get(entity_id).state == STATE_HOME

    mock_wifi_clients.return_value = []
    freezer.tick(31)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert entity_registry.async_get(entity_id).disabled_by is None
    assert hass.states.get(entity_id).state == STATE_NOT_HOME

    mock_wifi_clients.side_effect = OpenWrtUbusCommunicationError("Router unavailable")
    freezer.tick(31)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert entity_registry.async_get(entity_id) is not None
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    mock_wifi_clients.side_effect = None
    flow = await hass.config_entries.options.async_init(second.entry_id)
    await hass.config_entries.options.async_configure(
        flow["flow_id"], user_input={**second.options, CONF_TRACKING_MODE: "aliases_only"}
    )
    await hass.async_block_till_done()
    assert entity_registry.async_get(entity_id) is not None
    freezer.tick(31)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert entity_registry.async_get(entity_id) is None
    assert hass.states.get(entity_id) is None
    assert device_registry.async_get(device.id) is not None
    assert entity_registry.async_get(other_entity.entity_id) == other_entity

    flow = await hass.config_entries.options.async_init(first.entry_id)
    await hass.config_entries.options.async_configure(
        flow["flow_id"], user_input={**first.options, CONF_TRACKING_MODE: "known_or_alias"}
    )
    await hass.async_block_till_done()
    restored = entity_registry.async_get(entity_id)
    assert restored is not None
    assert restored.id == original.id
    assert restored.name == original.name
    assert restored.icon == original.icon
    assert hass.states.get(entity_id).state == STATE_NOT_HOME

    flow = await hass.config_entries.options.async_init(second.entry_id)
    await hass.config_entries.options.async_configure(
        flow["flow_id"], user_input={**second.options, CONF_TRACKING_MODE: "all"}
    )
    await hass.async_block_till_done()
    flow = await hass.config_entries.options.async_init(first.entry_id)
    await hass.config_entries.options.async_configure(
        flow["flow_id"], user_input={**first.options, CONF_ALIAS_MAPPING_UI: f"kitchen_device: {KNOWN_MAC}"}
    )
    await hass.async_block_till_done()
    assert entity_registry.async_get(entity_id) is None
    assert hass.states.get("device_tracker.kitchen_device").state == STATE_NOT_HOME
    for entry in entries:
        assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.integration
@pytest.mark.parametrize("initial_mode", ["aliases_only", "all"])
@pytest.mark.parametrize("disabler", [er.RegistryEntryDisabler.INTEGRATION, er.RegistryEntryDisabler.USER])
async def test_cleanup_existing_filtered_tracker(
    *,
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_wifi_clients: AsyncMock,
    initial_mode: str,
    disabler: er.RegistryEntryDisabler,
) -> None:
    """Clean up legacy flags without overriding user settings on recreation."""
    source_entry = MockConfigEntry(domain="test", unique_id="known-device-source")
    source_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=source_entry.entry_id, connections={(dr.CONNECTION_NETWORK_MAC, KNOWN_MAC)}
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="router-office.lan",
        version=3,
        data={CONF_HOST: "router-office.lan", CONF_USERNAME: "root", CONF_PASSWORD: "test-password"},
        options={CONF_TRACKING_MODE: initial_mode, CONF_MAPPING_SOURCE: "ui", CONF_ALIAS_MAPPING_UI: ""},
    )
    entry.add_to_hass(hass)
    hider = er.RegistryEntryHider(disabler.value)
    original = entity_registry.async_get_or_create(
        "device_tracker",
        DOMAIN,
        f"mac_{KNOWN_MAC}",
        config_entry=entry,
        disabled_by=disabler,
        hidden_by=hider,
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    if initial_mode == "all":
        assert entity_registry.async_get(original.entity_id) is not None
        flow = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.config_entries.options.async_configure(
            flow["flow_id"], user_input={**entry.options, CONF_TRACKING_MODE: "aliases_only"}
        )
        await hass.async_block_till_done()
    assert entity_registry.async_get(original.entity_id) is None
    assert hass.states.get(original.entity_id) is None

    mock_wifi_clients.return_value = [{"mac": KNOWN_MAC, "authorized": True}]
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        flow["flow_id"], user_input={**entry.options, CONF_TRACKING_MODE: "known_or_alias"}
    )
    await hass.async_block_till_done()
    restored = entity_registry.async_get(original.entity_id)
    assert restored is not None
    assert restored.id == original.id
    if disabler is er.RegistryEntryDisabler.USER:
        assert restored.disabled_by is disabler
        assert restored.hidden_by is hider
        assert hass.states.get(original.entity_id) is None
    else:
        assert restored.disabled_by is None
        assert restored.hidden_by is None
        assert hass.states.get(original.entity_id).state == STATE_HOME
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
