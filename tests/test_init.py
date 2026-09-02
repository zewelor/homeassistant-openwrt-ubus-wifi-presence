"""Tests for OpenWrt Ubus WiFi Presence config-entry lifecycle."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openwrt_ubus.const import CONF_ENDPOINT, CONF_USE_HTTPS, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.exceptions import ConfigEntryNotReady


def _entry(host: str, unique_id: str, *, version: int = 3) -> MockConfigEntry:
    """Return a complete OpenWrt config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"OpenWrt Ubus WiFi Presence ({host})",
        unique_id=unique_id,
        version=version,
        data={
            CONF_HOST: host,
            CONF_USE_HTTPS: False,
            CONF_ENDPOINT: "ubus",
            CONF_USERNAME: "root",
            CONF_PASSWORD: "secret",
            CONF_VERIFY_SSL: False,
        },
    )


def _coordinator() -> MagicMock:
    """Return a coordinator mock for setup lifecycle tests."""
    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    return coordinator


async def test_entries_share_managers_through_runtime_data(hass) -> None:
    """Test domain managers are shared without storing runtime state in hass.data."""
    first_entry = _entry("router-office.lan", "11:22:33:44:55:66")
    second_entry = _entry("router-kitchen.lan", "AA:BB:CC:DD:EE:FF")
    first_entry.add_to_hass(hass)
    second_entry.add_to_hass(hass)
    first_client = AsyncMock()
    second_client = AsyncMock()
    first_coordinator = _coordinator()
    second_coordinator = _coordinator()
    both_refreshes_started = asyncio.Event()
    allow_refreshes_to_finish = asyncio.Event()
    refresh_count = 0

    async def wait_for_concurrent_refreshes() -> None:
        nonlocal refresh_count
        refresh_count += 1
        if refresh_count == 2:
            both_refreshes_started.set()
        await allow_refreshes_to_finish.wait()

    first_coordinator.async_config_entry_first_refresh.side_effect = wait_for_concurrent_refreshes
    second_coordinator.async_config_entry_first_refresh.side_effect = wait_for_concurrent_refreshes

    with (
        patch("custom_components.openwrt_ubus.OpenWrtUbusClient", side_effect=[first_client, second_client]),
        patch(
            "custom_components.openwrt_ubus.OpenWrtUbusWifiPresenceCoordinator",
            side_effect=[first_coordinator, second_coordinator],
        ),
        patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()),
        patch.object(hass.config_entries, "async_unload_platforms", AsyncMock(return_value=True)),
    ):
        setup_task = hass.async_create_task(
            hass.config_entries.async_setup(first_entry.entry_id),
            "setup concurrent OpenWrt entries",
        )
        await both_refreshes_started.wait()

        assert first_entry.runtime_data.device_tracker_manager is second_entry.runtime_data.device_tracker_manager
        assert first_entry.runtime_data.ssid_presence_manager is second_entry.runtime_data.ssid_presence_manager

        allow_refreshes_to_finish.set()
        assert await setup_task

        assert first_entry.state is ConfigEntryState.LOADED
        assert second_entry.state is ConfigEntryState.LOADED

        assert DOMAIN not in hass.data

        assert await hass.config_entries.async_unload(first_entry.entry_id)
        assert await hass.config_entries.async_unload(second_entry.entry_id)

    first_client.close.assert_awaited_once()
    second_client.close.assert_awaited_once()


async def test_failed_first_refresh_closes_remote_session(hass) -> None:
    """Test setup failure does not leave a remote ubus session behind."""
    entry = _entry("router-office.lan", "11:22:33:44:55:66")
    entry.add_to_hass(hass)
    client = AsyncMock()
    coordinator = _coordinator()
    coordinator.async_config_entry_first_refresh.side_effect = ConfigEntryNotReady("offline")

    with (
        patch("custom_components.openwrt_ubus.OpenWrtUbusClient", return_value=client),
        patch("custom_components.openwrt_ubus.OpenWrtUbusWifiPresenceCoordinator", return_value=coordinator),
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_RETRY
    client.close.assert_awaited_once()
    assert not hasattr(entry, "runtime_data")


async def test_legacy_entries_are_rejected_without_migration(hass) -> None:
    """Test the documented 0.6 clean-break upgrade contract."""
    entry = _entry("router-office.lan", "router-office.lan", version=2)
    entry.add_to_hass(hass)

    with patch("custom_components.openwrt_ubus.OpenWrtUbusClient") as client_class:
        await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.MIGRATION_ERROR
    client_class.assert_not_called()
