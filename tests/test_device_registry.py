"""Regression tests for orphaned OpenWrt WiFi presence devices."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openwrt_ubus.api import OpenWrtUbusClient
from custom_components.openwrt_ubus.const import CONF_ALIAS_MAPPING_UI, CONF_MAPPING_SOURCE, CONF_TRACKING_MODE, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er


@pytest.mark.integration
@pytest.mark.parametrize("cleanup_on_reload", [False, True])
@pytest.mark.parametrize("disabled_by", [None, er.RegistryEntryDisabler.USER])
async def test_cleanup_preexisting_empty_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    cleanup_on_reload: bool,
    disabled_by: er.RegistryEntryDisabler | None,
) -> None:
    """Remove old empty devices while preserving seven entities and foreign MAC matches."""
    source_entry = MockConfigEntry(domain="test", unique_id="known-device-source")
    source_entry.add_to_hass(hass)
    aliases = {
        "living_room_sensor": "11:22:33:44:55:66",
        "bedroom_lamp": "AA:BB:CC:DD:EE:FF",
        "kitchen_device": "22:33:44:55:66:77",
    }
    ssids = {f"wlan{index}": f"MyNetwork{index}" for index in range(4)}
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="02:00:00:00:00:01",
        version=3,
        data={CONF_HOST: "router-office.lan", CONF_USERNAME: "root", CONF_PASSWORD: "test-password"},
        options={
            CONF_TRACKING_MODE: "aliases_only",
            CONF_MAPPING_SOURCE: "ui",
            CONF_ALIAS_MAPPING_UI: "\n".join(f"{alias}: {mac}" for alias, mac in aliases.items()),
        },
    )
    entry.add_to_hass(hass)
    active_devices = []
    active_entities = []
    for alias, mac in aliases.items():
        device = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, mac)},
            name=alias,
        )
        device = device_registry.async_update_device(device.id, name_by_user=f"Custom {alias}")
        active_devices.append(device)
        entity = entity_registry.async_get_or_create(
            "device_tracker",
            DOMAIN,
            f"alias_{alias}",
            config_entry=entry,
            device_id=device.id,
            suggested_object_id=alias,
            disabled_by=disabled_by,
        )
        active_entities.append(entity_registry.async_update_entity(entity.entity_id, name=f"Custom {alias}"))

    with (
        patch.object(
            OpenWrtUbusClient,
            "get_wifi_ssid_inventory",
            new=AsyncMock(return_value=(ssids, set(ssids.values()), True)),
        ),
        patch.object(OpenWrtUbusClient, "get_iwinfo_ap_devices", new=AsyncMock(return_value=list(ssids))),
        patch.object(OpenWrtUbusClient, "get_iwinfo_assoclist", new=AsyncMock(return_value=[])),
    ):
        if cleanup_on_reload:
            assert await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        empty_devices = []
        foreign_devices = []
        foreign_entities = []
        for index in range(20):
            mac = f"02:00:00:00:01:{index:02X}"
            empty_devices.append(
                device_registry.async_get_or_create(
                    config_entry_id=entry.entry_id, connections={(dr.CONNECTION_NETWORK_MAC, mac)}
                )
            )
            foreign_device = device_registry.async_get_or_create(
                config_entry_id=source_entry.entry_id, connections={(dr.CONNECTION_NETWORK_MAC, mac)}
            )
            foreign_devices.append(foreign_device)
            if index % 2 == 0:
                foreign_entities.append(
                    entity_registry.async_get_or_create(
                        "sensor", "test", f"source_{index}", config_entry=source_entry, device_id=foreign_device.id
                    )
                )

        if cleanup_on_reload:
            assert await hass.config_entries.async_reload(entry.entry_id)
        else:
            assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert all(device_registry.async_get(device.id) is None for device in empty_devices)
        assert {device.id for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id)} == {
            device.id for device in active_devices
        }
        assert all(device_registry.async_get(device.id) == device for device in foreign_devices)
        for original_device in active_devices:
            current_device = device_registry.async_get(original_device.id)
            assert current_device is not None
            assert current_device.name_by_user == original_device.name_by_user
            assert current_device.connections == original_device.connections
            assert current_device.config_entry_id == original_device.config_entry_id
        assert all(entity_registry.async_get(entity.entity_id) == entity for entity in foreign_entities)
        for original in active_entities:
            current = entity_registry.async_get(original.entity_id)
            assert current is not None
            assert (current.id, current.unique_id, current.name, current.device_id, current.disabled_by) == (
                original.id,
                original.unique_id,
                original.name,
                original.device_id,
                original.disabled_by,
            )
            if disabled_by is None:
                assert hass.states.get(original.entity_id).state == STATE_NOT_HOME
            else:
                assert hass.states.get(original.entity_id) is None

        remaining_entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        assert len(remaining_entities) == 7
        assert sum(entity.domain == "binary_sensor" for entity in remaining_entities) == 4
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert {
            entity.entity_id: (entity.id, entity.unique_id, entity.name, entity.device_id, entity.disabled_by)
            for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        } == {
            entity.entity_id: (entity.id, entity.unique_id, entity.name, entity.device_id, entity.disabled_by)
            for entity in remaining_entities
        }
        assert all(device_registry.async_get(device.id) is not None for device in active_devices)
        assert all(device_registry.async_get(device.id) == device for device in foreign_devices)
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
