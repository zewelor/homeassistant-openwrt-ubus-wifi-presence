"""Entity registry helpers for global WiFi device trackers."""

from __future__ import annotations

from custom_components.openwrt_ubus.const import DOMAIN
from homeassistant.helpers import entity_registry as er

_PLATFORM_DOMAIN = "device_tracker"


def _integration_tracker_entries(entity_registry: er.EntityRegistry) -> list[er.RegistryEntry]:
    """Return all device tracker registry entries owned by this integration."""
    return [
        entry
        for entry in entity_registry.entities.values()
        if entry.domain == _PLATFORM_DOMAIN and entry.platform == DOMAIN
    ]


def _clear_integration_visibility(
    entity_registry: er.EntityRegistry,
    entry: er.RegistryEntry,
) -> er.RegistryEntry:
    """Clear legacy visibility flags controlled by this integration."""
    clear_disabled = entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION
    clear_hidden = entry.hidden_by == er.RegistryEntryHider.INTEGRATION
    if clear_disabled and clear_hidden:
        return entity_registry.async_update_entity(entry.entity_id, disabled_by=None, hidden_by=None)
    if clear_disabled:
        return entity_registry.async_update_entity(entry.entity_id, disabled_by=None)
    if clear_hidden:
        return entity_registry.async_update_entity(entry.entity_id, hidden_by=None)
    return entry


def bind_tracker_registry_entry(
    entity_registry: er.EntityRegistry,
    *,
    entity_key: str,
    owner_entry_id: str,
) -> None:
    """Bind an existing global tracker to its current owner config entry."""
    entity_id = entity_registry.async_get_entity_id(_PLATFORM_DOMAIN, DOMAIN, entity_key)
    if entity_id is None or (entry := entity_registry.async_get(entity_id)) is None:
        return

    move_entry = entry.config_entry_id != owner_entry_id
    clear_disabled = entry.disabled_by == er.RegistryEntryDisabler.CONFIG_ENTRY
    if move_entry and clear_disabled:
        entity_registry.async_update_entity(
            entry.entity_id,
            config_entry_id=owner_entry_id,
            disabled_by=None,
        )
    elif move_entry:
        entity_registry.async_update_entity(entry.entity_id, config_entry_id=owner_entry_id)
    elif clear_disabled:
        entity_registry.async_update_entity(entry.entity_id, disabled_by=None)


def sync_tracker_registry(
    entity_registry: er.EntityRegistry,
    *,
    desired_keys: set[str],
    authoritative: bool,
    keep_unobserved_mac_trackers: bool,
    aliased_mac_keys: set[str],
) -> None:
    """Remove excluded trackers without deleting offline or uncertain clients."""
    for entry in _integration_tracker_entries(entity_registry):
        if entry.unique_id in desired_keys or (
            keep_unobserved_mac_trackers
            and entry.unique_id.startswith("mac_")
            and entry.unique_id not in aliased_mac_keys
        ):
            _clear_integration_visibility(entity_registry, entry)
        elif authoritative:
            # Home Assistant remembers deleted entries, including visibility flags.
            _clear_integration_visibility(entity_registry, entry)
            entity_registry.async_remove(entry.entity_id)
