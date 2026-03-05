"""Device tracker platform for OpenWrt Ubus WiFi Presence."""

from __future__ import annotations

from collections.abc import Mapping

from custom_components.openwrt_ubus.const import CONF_HOST, DOMAIN
from custom_components.openwrt_ubus.data import OpenWrtUbusWifiPresenceConfigEntry, TrackerTarget
from custom_components.openwrt_ubus.device_tracker.wifi_device import OpenWrtUbusWifiPresenceDeviceTracker
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback


def _extract_entity_key(unique_id: str, host: str) -> str | None:
    """Extract integration entity key from unique_id."""
    prefix = f"{host}_"
    if not unique_id.startswith(prefix):
        return None
    return unique_id.removeprefix(prefix)


def _registry_entries_by_key(
    entity_registry: er.EntityRegistry,
    config_entry_id: str,
    host: str,
) -> dict[str, er.RegistryEntry]:
    """Return registry entries for this platform indexed by entity key."""
    entries_by_key: dict[str, er.RegistryEntry] = {}
    for existing in er.async_entries_for_config_entry(entity_registry, config_entry_id):
        if existing.domain != "device_tracker" or existing.platform != DOMAIN or not existing.unique_id:
            continue
        entity_key = _extract_entity_key(existing.unique_id, host)
        if entity_key is None:
            continue
        entries_by_key[entity_key] = existing
    return entries_by_key


def _sync_registry_visibility(
    entity_registry: er.EntityRegistry,
    entries_by_key: Mapping[str, er.RegistryEntry],
    desired_keys: set[str],
) -> None:
    """Enable desired entries and disable entries outside current filter."""
    for entity_key, registry_entry in entries_by_key.items():
        if registry_entry.disabled_by not in (None, er.RegistryEntryDisabler.INTEGRATION):
            continue
        if registry_entry.hidden_by not in (None, er.RegistryEntryHider.INTEGRATION):
            continue

        should_be_enabled = entity_key in desired_keys
        if should_be_enabled:
            clear_disabled = registry_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION
            clear_hidden = registry_entry.hidden_by == er.RegistryEntryHider.INTEGRATION
            if clear_disabled and clear_hidden:
                entity_registry.async_update_entity(registry_entry.entity_id, disabled_by=None, hidden_by=None)
            elif clear_disabled:
                entity_registry.async_update_entity(registry_entry.entity_id, disabled_by=None)
            elif clear_hidden:
                entity_registry.async_update_entity(registry_entry.entity_id, hidden_by=None)
        else:
            set_disabled = registry_entry.disabled_by is None
            set_hidden = registry_entry.hidden_by is None
            if set_disabled and set_hidden:
                entity_registry.async_update_entity(
                    registry_entry.entity_id,
                    disabled_by=er.RegistryEntryDisabler.INTEGRATION,
                    hidden_by=er.RegistryEntryHider.INTEGRATION,
                )
            elif set_disabled:
                entity_registry.async_update_entity(
                    registry_entry.entity_id,
                    disabled_by=er.RegistryEntryDisabler.INTEGRATION,
                )
            elif set_hidden:
                entity_registry.async_update_entity(
                    registry_entry.entity_id,
                    hidden_by=er.RegistryEntryHider.INTEGRATION,
                )


async def async_setup_entry(
    hass,
    entry: OpenWrtUbusWifiPresenceConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WiFi device tracker entities for one config entry."""
    coordinator = entry.runtime_data.coordinator
    host = entry.data[CONF_HOST]
    active_entities: dict[str, OpenWrtUbusWifiPresenceDeviceTracker] = {}
    entity_registry = er.async_get(hass)

    def _build_entities(
        targets: Mapping[str, TrackerTarget],
        entries_by_key: Mapping[str, er.RegistryEntry],
    ) -> list[OpenWrtUbusWifiPresenceDeviceTracker]:
        blocked_disablers = {
            er.RegistryEntryDisabler.CONFIG_ENTRY,
            er.RegistryEntryDisabler.DEVICE,
            er.RegistryEntryDisabler.HASS,
            er.RegistryEntryDisabler.USER,
        }
        new_entities: list[OpenWrtUbusWifiPresenceDeviceTracker] = []
        for entity_key in sorted(targets):
            if entity_key in active_entities:
                continue
            registry_entry = entries_by_key.get(entity_key)
            if registry_entry and registry_entry.disabled_by in blocked_disablers:
                continue
            tracker = OpenWrtUbusWifiPresenceDeviceTracker(coordinator, entry, entity_key)
            active_entities[entity_key] = tracker
            new_entities.append(tracker)
        return new_entities

    desired_targets = coordinator.tracker_targets
    desired_keys = set(desired_targets)
    entries_by_key = _registry_entries_by_key(entity_registry, entry.entry_id, host)
    _sync_registry_visibility(entity_registry, entries_by_key, desired_keys)
    entries_by_key = _registry_entries_by_key(entity_registry, entry.entry_id, host)

    initial_entities = _build_entities(desired_targets, entries_by_key)
    if initial_entities:
        async_add_entities(initial_entities)

    def _handle_coordinator_update() -> None:
        desired_targets = coordinator.tracker_targets
        desired_keys = set(desired_targets)
        entries = _registry_entries_by_key(entity_registry, entry.entry_id, host)
        _sync_registry_visibility(entity_registry, entries, desired_keys)
        refreshed_entries = _registry_entries_by_key(entity_registry, entry.entry_id, host)
        new_entities = _build_entities(desired_targets, refreshed_entries)
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_handle_coordinator_update))
