"""Binary sensor platform for OpenWrt Ubus WiFi Presence."""

from __future__ import annotations

from collections.abc import Callable
from hashlib import sha1

from custom_components.openwrt_ubus.const import DOMAIN
from custom_components.openwrt_ubus.coordinator import OpenWrtUbusWifiPresenceCoordinator
from custom_components.openwrt_ubus.data import OpenWrtUbusWifiPresenceConfigEntry, WifiPresenceDevice
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

_SSID_UNIQUE_ID_PREFIX = "openwrt_wifi_ssid_presence_"

PARALLEL_UPDATES = 0


def _normalize_ssid(ssid: str) -> str:
    """Normalize WiFi SSID values used as entity keys."""
    return ssid.strip()


def _ssid_unique_id(ssid: str) -> str:
    """Return the stable unique ID for one WiFi SSID sensor."""
    ssid_hash = sha1(ssid.encode(), usedforsecurity=False).hexdigest()[:12]
    return f"{_SSID_UNIQUE_ID_PREFIX}{ssid_hash}"


class OpenWrtUbusSsidPresenceBinarySensor(BinarySensorEntity):
    """Binary sensor that is on when any client is connected to one WiFi SSID."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, manager: OpenWrtUbusSsidPresenceManager, ssid: str) -> None:
        """Initialize the WiFi SSID presence sensor."""
        self._manager = manager
        self._ssid = ssid
        slug = slugify(ssid, separator="_")
        self._attr_name = f"WiFi {ssid} Presence"
        self._attr_unique_id = _ssid_unique_id(ssid)
        self._attr_suggested_object_id = f"openwrt_wifi_{slug}_presence"

    async def async_added_to_hass(self) -> None:
        """Register the entity after Home Assistant accepted it."""
        await super().async_added_to_hass()
        self._manager.async_entity_added(self)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister the entity when Home Assistant removes it."""
        self._manager.async_entity_removed(self)
        await super().async_will_remove_from_hass()

    @property
    def ssid(self) -> str:
        """Return the WiFi SSID represented by this sensor."""
        return self._ssid

    @property
    def is_on(self) -> bool:
        """Return true when at least one client is connected to this WiFi SSID."""
        return self._manager.connected_count_for_ssid(self._ssid) > 0

    @property
    def available(self) -> bool:
        """Return true when all enabled routers have fresh coordinator data."""
        return self._manager.all_updates_successful

    @property
    def extra_state_attributes(self) -> dict[str, str | int]:
        """Return attributes for diagnostics and automations."""
        return {
            "ssid": self._ssid,
            "connected_clients": self._manager.connected_count_for_ssid(self._ssid),
        }


class OpenWrtUbusSsidPresenceManager:
    """Manage global WiFi SSID presence sensors across all integration entries."""

    def __init__(self, hass) -> None:
        """Initialize manager."""
        self.hass = hass
        self._entities_by_ssid: dict[str, OpenWrtUbusSsidPresenceBinarySensor] = {}
        self._pending_ssids: set[str] = set()
        self._coordinators: dict[str, OpenWrtUbusWifiPresenceCoordinator] = {}
        self._coordinator_unsubscribes: dict[str, Callable[[], None]] = {}
        self._async_add_entities_by_entry: dict[str, AddEntitiesCallback] = {}
        self._owner_entry_id: str | None = None

    async def async_register_entry(
        self,
        entry: OpenWrtUbusWifiPresenceConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Register one config entry coordinator for updates."""
        self._async_add_entities_by_entry[entry.entry_id] = async_add_entities
        if self._owner_entry_id is None:
            self._owner_entry_id = entry.entry_id

        if entry.entry_id in self._coordinator_unsubscribes:
            self._sync_ssid_entities()
            return

        coordinator = entry.runtime_data.coordinator
        self._coordinators[entry.entry_id] = coordinator
        unsub = coordinator.async_add_listener(self._handle_coordinator_update)
        self._coordinator_unsubscribes[entry.entry_id] = unsub
        entry.async_on_unload(lambda: self._async_unregister_entry(entry.entry_id))

        self._sync_ssid_entities()

    def _async_unregister_entry(self, entry_id: str) -> None:
        """Unregister one config entry listener."""
        unsub = self._coordinator_unsubscribes.pop(entry_id, None)
        if unsub:
            unsub()
        self._coordinators.pop(entry_id, None)
        self._async_add_entities_by_entry.pop(entry_id, None)
        if self._owner_entry_id == entry_id:
            self._owner_entry_id = next(iter(self._async_add_entities_by_entry), None)
        self._handle_coordinator_update()

    @callback
    def async_entity_added(self, entity: OpenWrtUbusSsidPresenceBinarySensor) -> None:
        """Track an entity only after Home Assistant added it."""
        self._pending_ssids.discard(entity.ssid)
        self._entities_by_ssid[entity.ssid] = entity

    @callback
    def async_entity_removed(self, entity: OpenWrtUbusSsidPresenceBinarySensor) -> None:
        """Stop tracking an entity removed by Home Assistant."""
        # A delayed callback from an old platform must not remove its replacement.
        if self._entities_by_ssid.get(entity.ssid) is entity:
            self._entities_by_ssid.pop(entity.ssid)

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

    def _iter_coordinator_data(self) -> list[dict[str, WifiPresenceDevice]]:
        """Return fresh coordinator data for all loaded entries."""
        datasets: list[dict[str, WifiPresenceDevice]] = []
        for coordinator in self._coordinators.values():
            if not coordinator.last_update_success:
                continue
            data = getattr(coordinator, "data", None)
            if isinstance(data, dict):
                datasets.append(data)
        return datasets

    def _current_ssids(self) -> set[str]:
        """Return all configured or currently observed WiFi SSIDs."""
        ssids: set[str] = set()
        for coordinator in self._coordinators.values():
            if not coordinator.last_update_success:
                continue

            for known_ssid in coordinator.known_ssids:
                ssid = _normalize_ssid(known_ssid)
                if ssid:
                    ssids.add(ssid)

            data = getattr(coordinator, "data", None)
            if not isinstance(data, dict):
                continue

            devices: dict[str, WifiPresenceDevice] = data
            for device in devices.values():
                if not isinstance(device.ssid, str):
                    continue
                ssid = _normalize_ssid(device.ssid)
                if ssid:
                    ssids.add(ssid)
        return ssids

    def connected_count_for_ssid(self, ssid: str) -> int:
        """Count unique associated clients for one WiFi SSID across all routers."""
        connected_macs: set[str] = set()
        for devices in self._iter_coordinator_data():
            for mac, device in devices.items():
                if not isinstance(device.ssid, str) or _normalize_ssid(device.ssid) != ssid:
                    continue
                connected_macs.add(mac)
        return len(connected_macs)

    def _remove_stale_ssid_entities(self, current_ssids: set[str]) -> None:
        """Remove sensors for WiFi SSIDs that no longer exist."""
        current_unique_ids = {_ssid_unique_id(ssid) for ssid in current_ssids}
        entity_registry = er.async_get(self.hass)

        # Ownership may already have moved or the old config entry may be gone.
        # The platform and dedicated prefix identify this manager's entries.
        for registry_entry in list(entity_registry.entities.values()):
            if (
                registry_entry.domain == "binary_sensor"
                and registry_entry.platform == DOMAIN
                and registry_entry.unique_id.startswith(_SSID_UNIQUE_ID_PREFIX)
                and registry_entry.unique_id not in current_unique_ids
            ):
                entity_registry.async_remove(registry_entry.entity_id)

    def _ssid_entity_needs_add(self, ssid: str) -> bool:
        """Return whether Home Assistant should process this WiFi SSID entity."""
        if ssid in self._entities_by_ssid or ssid in self._pending_ssids:
            return False

        entity_registry = er.async_get(self.hass)
        entity_id = entity_registry.async_get_entity_id("binary_sensor", DOMAIN, _ssid_unique_id(ssid))
        if entity_id is None:
            return True

        registry_entry = entity_registry.async_get(entity_id)
        return bool(
            registry_entry and (not registry_entry.disabled or registry_entry.config_entry_id != self._owner_entry_id)
        )

    def _sync_ssid_entities(self) -> None:
        """Reconcile entities with currently reported WiFi SSIDs."""
        if self._owner_entry_id is None:
            return
        async_add_entities = self._async_add_entities_by_entry.get(self._owner_entry_id)
        if async_add_entities is None:
            return

        current_ssids = self._current_ssids()
        if self.all_updates_successful and all(
            coordinator.ssid_inventory_complete for coordinator in self._coordinators.values()
        ):
            self._remove_stale_ssid_entities(current_ssids)

        new_entities: list[Entity] = []
        for ssid in sorted(current_ssids):
            if not self._ssid_entity_needs_add(ssid):
                continue
            entity = OpenWrtUbusSsidPresenceBinarySensor(self, ssid)
            self._pending_ssids.add(ssid)
            # Home Assistant runs async_on_remove for rejected additions too.
            entity.async_on_remove(lambda ssid=ssid: self._pending_ssids.discard(ssid))
            new_entities.append(entity)

        if new_entities:
            async_add_entities(new_entities)

    def _handle_coordinator_update(self) -> None:
        """Update entities after coordinator refresh."""
        self._sync_ssid_entities()
        for entity in self._entities_by_ssid.values():
            entity.async_write_ha_state()


async def async_setup_entry(
    hass,
    entry: OpenWrtUbusWifiPresenceConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up global WiFi SSID presence binary sensors."""
    del hass
    manager = entry.runtime_data.ssid_presence_manager
    await manager.async_register_entry(entry, async_add_entities)
