"""Entity registry helpers for global WiFi device trackers."""

from __future__ import annotations

from collections.abc import Collection, Mapping

from custom_components.openwrt_ubus.const import DOMAIN
from custom_components.openwrt_ubus.data import TrackerTarget, TrackerTargetType
from homeassistant.helpers import entity_registry as er

_PLATFORM_DOMAIN = "device_tracker"


def _integration_tracker_entries(entity_registry: er.EntityRegistry) -> list[er.RegistryEntry]:
    """Return all device tracker registry entries owned by this integration."""
    return [
        entry
        for entry in entity_registry.entities.values()
        if entry.domain == _PLATFORM_DOMAIN and entry.platform == DOMAIN
    ]


def _normalize_registry_mac(value: str) -> str | None:
    """Normalize a possible legacy MAC unique ID without depending on a client."""
    stripped = value.replace("-", "").replace(":", "").strip().upper()
    if len(stripped) != 12 or any(character not in "0123456789ABCDEF" for character in stripped):
        return None
    return ":".join(stripped[index : index + 2] for index in range(0, 12, 2))


def _matches_alias_identity(entry: er.RegistryEntry, target: TrackerTarget) -> bool:
    """Return whether registry metadata identifies a legacy alias entity."""
    if target.tracker_type != TrackerTargetType.ALIAS:
        return False
    alias_object_id = target.entity_key.removeprefix("alias_")
    return alias_object_id in (entry.suggested_object_id, entry.object_id_base)


def _set_integration_visibility(
    entity_registry: er.EntityRegistry,
    entry: er.RegistryEntry,
    *,
    visible: bool,
) -> er.RegistryEntry:
    """Change only visibility state controlled by this integration."""
    if visible:
        clear_disabled = entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION
        clear_hidden = entry.hidden_by == er.RegistryEntryHider.INTEGRATION
        if clear_disabled and clear_hidden:
            return entity_registry.async_update_entity(entry.entity_id, disabled_by=None, hidden_by=None)
        if clear_disabled:
            return entity_registry.async_update_entity(entry.entity_id, disabled_by=None)
        if clear_hidden:
            return entity_registry.async_update_entity(entry.entity_id, hidden_by=None)
        return entry

    set_disabled = entry.disabled_by is None
    set_hidden = entry.hidden_by is None
    if set_disabled and set_hidden:
        return entity_registry.async_update_entity(
            entry.entity_id,
            disabled_by=er.RegistryEntryDisabler.INTEGRATION,
            hidden_by=er.RegistryEntryHider.INTEGRATION,
        )
    if set_disabled:
        return entity_registry.async_update_entity(
            entry.entity_id,
            disabled_by=er.RegistryEntryDisabler.INTEGRATION,
        )
    if set_hidden:
        return entity_registry.async_update_entity(
            entry.entity_id,
            hidden_by=er.RegistryEntryHider.INTEGRATION,
        )
    return entry


def migrate_target_registry_entry(
    entity_registry: er.EntityRegistry,
    *,
    target: TrackerTarget,
    owner_entry_id: str,
    owner_host: str,
    hosts_by_entry_id: Mapping[str, str],
    legacy_macs: Collection[str],
    conflicting: bool,
) -> er.RegistryEntry | None:
    """Migrate one legacy per-router tracker to its global unique ID."""
    entries = _integration_tracker_entries(entity_registry)
    global_entry = next((entry for entry in entries if entry.unique_id == target.entity_key), None)
    historical_unique_ids = {f"{host}_{target.entity_key}" for host in hosts_by_entry_id.values()}
    owner_historical_unique_id = f"{owner_host}_{target.entity_key}"
    normalized_legacy_macs = set(legacy_macs)

    legacy_entries = [
        entry
        for entry in entries
        if entry.unique_id in historical_unique_ids
        or _normalize_registry_mac(entry.unique_id) in normalized_legacy_macs
        or _matches_alias_identity(entry, target)
    ]

    canonical = global_entry
    if canonical is None:
        historical_entries = [entry for entry in legacy_entries if entry.unique_id in historical_unique_ids]
        owner_entries = [entry for entry in historical_entries if entry.unique_id == owner_historical_unique_id]
        mac_entries = [
            entry for entry in legacy_entries if _normalize_registry_mac(entry.unique_id) in normalized_legacy_macs
        ]
        alias_identity_entries = [entry for entry in legacy_entries if _matches_alias_identity(entry, target)]
        if conflicting:
            candidates = alias_identity_entries or owner_entries or historical_entries
        elif target.tracker_type == TrackerTargetType.ALIAS:
            candidates = alias_identity_entries or mac_entries or owner_entries or historical_entries
        else:
            candidates = mac_entries or owner_entries or historical_entries
        if candidates:
            canonical = min(candidates, key=lambda entry: entry.entity_id)

    if canonical is not None:
        if canonical.unique_id != target.entity_key:
            canonical = entity_registry.async_update_entity(
                canonical.entity_id,
                config_entry_id=owner_entry_id,
                new_unique_id=target.entity_key,
            )
        elif canonical.config_entry_id != owner_entry_id:
            canonical = entity_registry.async_update_entity(
                canonical.entity_id,
                config_entry_id=owner_entry_id,
            )
        if canonical.disabled_by == er.RegistryEntryDisabler.CONFIG_ENTRY:
            canonical = entity_registry.async_update_entity(canonical.entity_id, disabled_by=None)
        canonical = _set_integration_visibility(entity_registry, canonical, visible=True)

    for duplicate in legacy_entries:
        if canonical is not None and duplicate.entity_id == canonical.entity_id:
            continue
        _set_integration_visibility(entity_registry, duplicate, visible=False)

    return canonical


def sync_tracker_registry_visibility(
    entity_registry: er.EntityRegistry,
    *,
    desired_keys: set[str],
    authoritative: bool,
) -> None:
    """Synchronize global tracker visibility without hiding uncertain targets."""
    for entry in _integration_tracker_entries(entity_registry):
        if entry.unique_id in desired_keys:
            _set_integration_visibility(entity_registry, entry, visible=True)
        elif authoritative:
            _set_integration_visibility(entity_registry, entry, visible=False)
