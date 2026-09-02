"""Global manager for OpenWrt WiFi device tracker entities."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta

from custom_components.openwrt_ubus.const import CONF_HOST, DOMAIN, LOGGER
from custom_components.openwrt_ubus.coordinator import OpenWrtUbusWifiPresenceCoordinator
from custom_components.openwrt_ubus.data import (
    OpenWrtUbusWifiPresenceConfigEntry,
    TrackerTarget,
    TrackerTargetSource,
    TrackerTargetType,
    WifiPresenceDevice,
)
from custom_components.openwrt_ubus.device_tracker.registry import (
    bind_tracker_registry_entry,
    sync_tracker_registry_visibility,
)
from custom_components.openwrt_ubus.device_tracker.wifi_device import OpenWrtUbusWifiPresenceDeviceTracker
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_TRACKER_MANAGER_KEY = "device_tracker_manager"


@dataclass(frozen=True, slots=True)
class OpenWrtUbusWifiPresenceTrackerObservation:
    """One selected association reported by a healthy router."""

    device: WifiPresenceDevice
    router: str


class OpenWrtUbusWifiPresenceDeviceTrackerManager:
    """Manage one global device tracker per target across all routers."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the global tracker manager."""
        self.hass = hass
        self._entities_by_key: dict[str, OpenWrtUbusWifiPresenceDeviceTracker] = {}
        self._pending_entities_by_key: dict[str, OpenWrtUbusWifiPresenceDeviceTracker] = {}
        self._coordinators: dict[str, OpenWrtUbusWifiPresenceCoordinator] = {}
        self._coordinator_unsubscribes: dict[str, Callable[[], None]] = {}
        self._async_add_entities_by_entry: dict[str, AddEntitiesCallback] = {}
        self._owner_entry_id: str | None = None
        self._targets: dict[str, TrackerTarget] = {}
        self._remembered_targets: dict[str, TrackerTarget] = {}
        self._conflict_macs: dict[str, frozenset[str]] = {}
        self._conflict_signatures: dict[str, tuple[tuple[str, str], ...]] = {}
        self._last_seen_router_by_key: dict[str, tuple[str, str]] = {}

    async def async_register_entry(
        self,
        entry: OpenWrtUbusWifiPresenceConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Register one router coordinator and its entity platform callback."""
        self._async_add_entities_by_entry[entry.entry_id] = async_add_entities
        if self._owner_entry_id is None:
            self._owner_entry_id = entry.entry_id

        if entry.entry_id not in self._coordinator_unsubscribes:
            coordinator = entry.runtime_data.coordinator
            self._coordinators[entry.entry_id] = coordinator
            self._coordinator_unsubscribes[entry.entry_id] = coordinator.async_add_listener(
                self._handle_coordinator_update
            )
            entry.async_on_unload(lambda: self._async_unregister_entry(entry.entry_id))

        self._handle_coordinator_update()

    @callback
    def _async_unregister_entry(self, entry_id: str) -> None:
        """Unregister one router after its entity platform unloads."""
        if unsubscribe := self._coordinator_unsubscribes.pop(entry_id, None):
            unsubscribe()
        self._coordinators.pop(entry_id, None)
        self._async_add_entities_by_entry.pop(entry_id, None)
        if self._owner_entry_id == entry_id:
            self._owner_entry_id = next(iter(self._async_add_entities_by_entry), None)
        if not self._coordinators:
            self._targets.clear()
            self._remembered_targets.clear()
            self._conflict_macs.clear()
            self._conflict_signatures.clear()
            self._last_seen_router_by_key.clear()
            return
        self._handle_coordinator_update()

    @callback
    def async_entity_added(self, entity: OpenWrtUbusWifiPresenceDeviceTracker) -> None:
        """Track an entity only after Home Assistant accepted it."""
        pending_entity = self._pending_entities_by_key.get(entity.entity_key)
        active_entity = self._entities_by_key.get(entity.entity_key)
        if active_entity is not None and active_entity is not entity:
            if pending_entity is entity:
                self._pending_entities_by_key.pop(entity.entity_key)
            return
        if pending_entity is not None and pending_entity is not entity:
            return
        if pending_entity is entity:
            self._pending_entities_by_key.pop(entity.entity_key)
        self._entities_by_key[entity.entity_key] = entity

    @callback
    def async_pending_entity_removed(self, entity: OpenWrtUbusWifiPresenceDeviceTracker) -> None:
        """Forget a pending entity only when the callback belongs to it."""
        if self._pending_entities_by_key.get(entity.entity_key) is entity:
            self._pending_entities_by_key.pop(entity.entity_key)

    @callback
    def async_entity_removed(self, entity: OpenWrtUbusWifiPresenceDeviceTracker) -> None:
        """Stop tracking an entity removed by Home Assistant."""
        if self._entities_by_key.get(entity.entity_key) is not entity:
            return
        self._entities_by_key.pop(entity.entity_key)
        if entity.owner_entry_id != self._owner_entry_id:
            # Wait until the old entity releases its state-machine ID before
            # handing the same registry identity to the replacement platform.
            self.hass.loop.call_soon(self._sync_tracker_entities)

    @property
    def all_updates_successful(self) -> bool:
        """Return true when every enabled router has fresh coordinator data."""
        enabled_entry_ids = {
            entry.entry_id for entry in self.hass.config_entries.async_entries(DOMAIN, include_disabled=False)
        }
        return (
            bool(enabled_entry_ids)
            and enabled_entry_ids == set(self._coordinators)
            and all(coordinator.last_update_success for coordinator in self._coordinators.values())
        )

    def target_for_key(self, entity_key: str) -> TrackerTarget | None:
        """Return the current or last known target definition."""
        return self._targets.get(entity_key) or self._remembered_targets.get(entity_key)

    def target_is_current(self, entity_key: str) -> bool:
        """Return whether a target is still part of the current global inventory."""
        return entity_key in self._targets

    def target_has_conflict(self, entity_key: str) -> bool:
        """Return whether routers disagree about an alias target MAC."""
        return entity_key in self._conflict_macs

    def resolved_mac_for_key(self, entity_key: str) -> str | None:
        """Return the unambiguous MAC currently represented by a tracker."""
        if self.target_has_conflict(entity_key):
            return None
        target = self.target_for_key(entity_key)
        return target.mac if target else None

    def current_observation_for_key(
        self,
        entity_key: str,
    ) -> OpenWrtUbusWifiPresenceTrackerObservation | None:
        """Return the preferred fresh association for one global target."""
        mac = self.resolved_mac_for_key(entity_key)
        if mac is None:
            return None

        candidates: list[
            tuple[
                tuple[bool, float, bool, float, str, str],
                OpenWrtUbusWifiPresenceTrackerObservation,
            ]
        ] = []
        for coordinator in self._coordinators.values():
            if not coordinator.last_update_success:
                continue
            data = getattr(coordinator, "data", None)
            if not isinstance(data, dict) or (device := data.get(mac)) is None:
                continue
            router = str(coordinator.entry.data[CONF_HOST])
            observation = OpenWrtUbusWifiPresenceTrackerObservation(device=device, router=router)
            candidates.append((self._observation_sort_key(coordinator, observation), observation))

        if not candidates:
            return None
        return min(candidates, key=lambda candidate: candidate[0])[1]

    def tracker_available(self, entity_key: str) -> bool:
        """Return whether the tracker can publish a certain presence state."""
        if self.target_has_conflict(entity_key):
            return False
        if self.current_observation_for_key(entity_key) is not None:
            return True
        return self.resolved_mac_for_key(entity_key) is not None and self.all_updates_successful

    def last_or_current_router_for_key(self, entity_key: str) -> str | None:
        """Return the current router or the last router that saw this target."""
        if observation := self.current_observation_for_key(entity_key):
            return observation.router
        last_seen = self._last_seen_router_by_key.get(entity_key)
        if last_seen is None:
            return None
        last_seen_mac, router = last_seen
        target = self.target_for_key(entity_key)
        if target is None or target.mac is None or target.mac == last_seen_mac:
            return router
        return None

    @staticmethod
    def _observation_sort_key(
        coordinator: OpenWrtUbusWifiPresenceCoordinator,
        observation: OpenWrtUbusWifiPresenceTrackerObservation,
    ) -> tuple[bool, float, bool, float, str, str]:
        """Prefer newest activity, then strongest signal and stable AP ordering."""
        last_update = coordinator.last_update_success_time
        inactive_ms = observation.device.inactive_ms
        effective_activity: datetime | None = None
        if isinstance(last_update, datetime) and inactive_ms is not None:
            effective_activity = last_update - timedelta(milliseconds=inactive_ms)

        signal_dbm = observation.device.signal_dbm
        return (
            effective_activity is None,
            -effective_activity.timestamp() if effective_activity is not None else 0.0,
            signal_dbm is None,
            -float(signal_dbm) if signal_dbm is not None else 0.0,
            observation.router,
            observation.device.ap_device,
        )

    @staticmethod
    def _target_preference(target: TrackerTarget) -> tuple[int, str, str]:
        """Prefer friendly known-device metadata over anonymous discovery."""
        source_rank = {
            TrackerTargetSource.ALIAS: 0,
            TrackerTargetSource.KNOWN: 1,
            TrackerTargetSource.ALL: 2,
        }
        return source_rank[target.source], target.display_name, target.entity_key

    def _rebuild_targets(self) -> None:
        """Build one deterministic global target inventory from all routers."""
        alias_candidates: dict[str, list[tuple[str, str, TrackerTarget]]] = {}
        mac_candidates: dict[str, list[TrackerTarget]] = {}

        for entry_id, coordinator in self._coordinators.items():
            router = str(coordinator.entry.data[CONF_HOST])
            for target in coordinator.tracker_targets.values():
                if target.tracker_type == TrackerTargetType.ALIAS:
                    alias_candidates.setdefault(target.entity_key, []).append((entry_id, router, target))
                else:
                    mac_candidates.setdefault(target.entity_key, []).append(target)

        targets: dict[str, TrackerTarget] = {}
        conflicts: dict[str, frozenset[str]] = {}
        conflict_signatures: dict[str, tuple[tuple[str, str], ...]] = {}
        aliased_macs: set[str] = set()

        for entity_key, candidates in alias_candidates.items():
            candidates.sort(key=lambda item: (item[1], item[0], item[2].display_name))
            macs = frozenset(target.mac for _, _, target in candidates if target.mac is not None)
            aliased_macs.update(macs)
            selected = candidates[0][2]
            if len(macs) > 1:
                conflicts[entity_key] = macs
                conflict_signatures[entity_key] = tuple(
                    sorted((router, target.mac or "unknown") for _, router, target in candidates)
                )
                selected = TrackerTarget(
                    entity_key=selected.entity_key,
                    tracker_type=selected.tracker_type,
                    source=selected.source,
                    display_name=selected.display_name,
                    mac=None,
                )
            targets[entity_key] = selected

        for entity_key, candidates in mac_candidates.items():
            candidate = min(candidates, key=self._target_preference)
            if candidate.mac in aliased_macs:
                continue
            targets[entity_key] = candidate

        self._log_conflict_transitions(conflict_signatures)
        self._targets = targets
        self._remembered_targets.update(targets)
        self._conflict_macs = conflicts
        self._conflict_signatures = conflict_signatures

    def _log_conflict_transitions(self, current: dict[str, tuple[tuple[str, str], ...]]) -> None:
        """Log alias conflicts once when they appear, change, or resolve."""
        for entity_key, signature in current.items():
            if self._conflict_signatures.get(entity_key) == signature:
                continue
            mappings = ", ".join(f"{router}={mac}" for router, mac in signature)
            LOGGER.error("Conflicting global tracker alias %s: %s", entity_key, mappings)
        for entity_key in self._conflict_signatures.keys() - current.keys():
            LOGGER.info("Global tracker alias conflict resolved for %s", entity_key)

    def _refresh_last_seen_routers(self) -> None:
        """Remember only routers backed by a current healthy observation."""
        for entity_key in self._targets:
            if self.target_has_conflict(entity_key):
                continue
            observation = self.current_observation_for_key(entity_key)
            if observation is not None:
                self._last_seen_router_by_key[entity_key] = (observation.device.mac, observation.router)

    def _entity_needs_add(self, entity_key: str, entity_registry: er.EntityRegistry) -> bool:
        """Return whether Home Assistant should process a tracker entity."""
        if entity_key in self._entities_by_key or entity_key in self._pending_entities_by_key:
            return False
        entity_id = entity_registry.async_get_entity_id("device_tracker", DOMAIN, entity_key)
        if entity_id is None:
            return True
        registry_entry = entity_registry.async_get(entity_id)
        return bool(registry_entry and not registry_entry.disabled)

    def _sync_tracker_entities(self) -> None:
        """Reconcile global tracker registry entries and entities."""
        owner_entry_id = self._owner_entry_id
        if owner_entry_id is None:
            return
        async_add_entities = self._async_add_entities_by_entry.get(owner_entry_id)
        owner_coordinator = self._coordinators.get(owner_entry_id)
        if async_add_entities is None or owner_coordinator is None:
            return
        if owner_coordinator.entry.state is ConfigEntryState.UNLOAD_IN_PROGRESS:
            return

        entity_registry = er.async_get(self.hass)
        for entity_key in sorted(self._targets):
            active_entity = self._entities_by_key.get(entity_key)
            if active_entity is not None and active_entity.owner_entry_id != owner_entry_id:
                continue
            bind_tracker_registry_entry(
                entity_registry,
                entity_key=entity_key,
                owner_entry_id=owner_entry_id,
            )

        sync_tracker_registry_visibility(
            entity_registry,
            desired_keys=set(self._targets),
            authoritative=self.all_updates_successful,
        )

        new_entities: list[Entity] = []
        for entity_key, target in sorted(self._targets.items()):
            if not self._entity_needs_add(entity_key, entity_registry):
                continue
            entity = OpenWrtUbusWifiPresenceDeviceTracker(
                manager=self,
                owner_entry_id=owner_entry_id,
                target=target,
            )
            self._pending_entities_by_key[entity_key] = entity
            entity.async_on_remove(lambda entity=entity: self.async_pending_entity_removed(entity))
            new_entities.append(entity)

        if new_entities:
            async_add_entities(new_entities)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Reconcile trackers and publish state after any router update."""
        self._rebuild_targets()
        self._refresh_last_seen_routers()
        self._sync_tracker_entities()
        for entity in list(self._entities_by_key.values()):
            entity.async_write_ha_state()


def get_device_tracker_manager(hass: HomeAssistant) -> OpenWrtUbusWifiPresenceDeviceTrackerManager | None:
    """Return the global tracker manager when initialized."""
    domain_data = hass.data.get(DOMAIN)
    if not isinstance(domain_data, Mapping):
        return None
    manager = domain_data.get(_TRACKER_MANAGER_KEY)
    if isinstance(manager, OpenWrtUbusWifiPresenceDeviceTrackerManager):
        return manager
    return None


def get_or_create_device_tracker_manager(hass: HomeAssistant) -> OpenWrtUbusWifiPresenceDeviceTrackerManager:
    """Return the global tracker manager, creating it on first platform setup."""
    if manager := get_device_tracker_manager(hass):
        return manager
    manager = OpenWrtUbusWifiPresenceDeviceTrackerManager(hass)
    hass.data.setdefault(DOMAIN, {})[_TRACKER_MANAGER_KEY] = manager
    return manager
