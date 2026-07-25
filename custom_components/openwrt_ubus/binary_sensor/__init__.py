"""Binary sensor platform for OpenWrt Ubus WiFi Presence."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from hashlib import sha1

from custom_components.openwrt_ubus.const import DOMAIN
from custom_components.openwrt_ubus.coordinator import OpenWrtUbusWifiPresenceCoordinator
from custom_components.openwrt_ubus.data import OpenWrtUbusWifiPresenceConfigEntry, WifiPresenceDevice
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

_BINARY_SENSOR_DOMAIN = "binary_sensor"
_SSID_MANAGER_KEY = "ssid_presence_manager"
_SSID_UNIQUE_ID_PREFIX = "openwrt_wifi_ssid_presence_"


def _normalize_ssid(ssid: str) -> str:
    """Normalize WiFi SSID values used as entity keys."""
    return ssid.strip()


def _ssid_unique_id(ssid: str) -> str:
    """Return the stable unique ID for one WiFi SSID sensor."""
    ssid_hash = sha1(ssid.encode(), usedforsecurity=False).hexdigest()[:12]
    return f"{_SSID_UNIQUE_ID_PREFIX}{ssid_hash}"


class OpenWrtUbusSsidPresenceBinarySensor(BinarySensorEntity):
    """Binary sensor that is on when a WiFi SSID has an associated client."""

    _attr_has_entity_name = True

    def __init__(self, ssid: str) -> None:
        """Initialize the WiFi SSID presence sensor."""
        self._ssid = ssid
        slug = slugify(ssid, separator="_")
        self._attr_name = f"WiFi {ssid} Presence"
        self._attr_unique_id = _ssid_unique_id(ssid)
        self._attr_suggested_object_id = f"openwrt_wifi_{slug}_presence"

    @property
    def ssid(self) -> str:
        """Return the WiFi SSID represented by this sensor."""
        return self._ssid

    @property
    def is_on(self) -> bool:
        """Return true when at least one client is connected to this WiFi SSID."""
        manager = _get_manager(self.hass)
        return bool(manager and manager.connected_count_for_ssid(self._ssid) > 0)

    @property
    def available(self) -> bool:
        """Return true when all registered routers have fresh coordinator data."""
        manager = _get_manager(self.hass)
        return bool(manager and manager.all_updates_successful)

    @property
    def extra_state_attributes(self) -> dict[str, str | int]:
        """Return attributes for diagnostics and automations."""
        manager = _get_manager(self.hass)
        connected_count = manager.connected_count_for_ssid(self._ssid) if manager else 0
        return {
            "ssid": self._ssid,
            "connected_clients": connected_count,
        }


class OpenWrtUbusSsidPresenceManager:
    """Manage global WiFi SSID presence sensors across integration entries."""

    def __init__(self, hass) -> None:
        """Initialize manager."""
        self.hass = hass
        self._entities_by_ssid: dict[str, OpenWrtUbusSsidPresenceBinarySensor] = {}
        self._coordinators: dict[str, OpenWrtUbusWifiPresenceCoordinator] = {}
        self._coordinator_unsubscribes: dict[str, Callable[[], None]] = {}
        self._async_add_entities_by_entry: dict[str, AddEntitiesCallback] = {}
        self._retained_ssids_by_entry: dict[str, set[str]] = {}
        self._owner_entry_id: str | None = None

    async def async_register_entry(
        self,
        entry: OpenWrtUbusWifiPresenceConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Register one config entry coordinator for updates."""
        self._retained_ssids_by_entry.pop(entry.entry_id, None)
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
        """Unregister one config entry while retaining its last known WiFi SSIDs."""
        unsub = self._coordinator_unsubscribes.pop(entry_id, None)
        if unsub:
            unsub()
        coordinator = self._coordinators.pop(entry_id, None)
        if coordinator is not None:
            self._retained_ssids_by_entry[entry_id] = self._ssids_for_coordinator(coordinator)
        self._async_add_entities_by_entry.pop(entry_id, None)
        if self._owner_entry_id == entry_id:
            self._entities_by_ssid.clear()
            self._owner_entry_id = next(iter(self._async_add_entities_by_entry), None)
        self._handle_coordinator_update()

    @property
    def all_updates_successful(self) -> bool:
        """Return true when every registered coordinator updated successfully."""
        return bool(self._coordinators) and all(
            coordinator.last_update_success for coordinator in self._coordinators.values()
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

    def _ssids_for_coordinator(self, coordinator: OpenWrtUbusWifiPresenceCoordinator) -> set[str]:
        """Return normalized WiFi SSIDs from one coordinator's latest stored data."""
        ssids = {_normalize_ssid(ssid) for ssid in coordinator.known_ssids if _normalize_ssid(ssid)}
        data = getattr(coordinator, "data", None)
        if not isinstance(data, dict):
            return ssids

        devices: dict[str, WifiPresenceDevice] = data
        for device in devices.values():
            if not isinstance(device.ssid, str):
                continue
            ssid = _normalize_ssid(device.ssid)
            if ssid:
                ssids.add(ssid)
        return ssids

    def _current_ssids(self) -> set[str]:
        """Return all currently confirmed or reload-retained WiFi SSIDs."""
        for entry_id in list(self._retained_ssids_by_entry):
            if self.hass.config_entries.async_get_entry(entry_id) is None:
                self._retained_ssids_by_entry.pop(entry_id)

        ssids: set[str] = set()
        for retained_ssids in self._retained_ssids_by_entry.values():
            ssids.update(retained_ssids)
        for coordinator in self._coordinators.values():
            if coordinator.last_update_success:
                ssids.update(self._ssids_for_coordinator(coordinator))
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
        """Remove WiFi SSID sensors absent from every successful router update."""
        desired_unique_ids = {_ssid_unique_id(ssid) for ssid in current_ssids}
        entity_registry = er.async_get(self.hass)
        stale_entity_ids: set[str] = set()

        for entry_id in self._async_add_entities_by_entry:
            for registry_entry in er.async_entries_for_config_entry(entity_registry, entry_id):
                if (
                    registry_entry.domain != _BINARY_SENSOR_DOMAIN
                    or registry_entry.platform != DOMAIN
                    or not registry_entry.unique_id.startswith(_SSID_UNIQUE_ID_PREFIX)
                    or registry_entry.unique_id in desired_unique_ids
                ):
                    continue
                stale_entity_ids.add(registry_entry.entity_id)

        for entity_id in sorted(stale_entity_ids):
            entity_registry.async_remove(entity_id)

        for ssid, entity in list(self._entities_by_ssid.items()):
            if entity.unique_id not in desired_unique_ids:
                self._entities_by_ssid.pop(ssid)

    def _sync_ssid_entities(self) -> None:
        """Reconcile global entities with WiFi SSIDs reported by all routers."""
        if self._owner_entry_id is None:
            return
        async_add_entities = self._async_add_entities_by_entry.get(self._owner_entry_id)
        if async_add_entities is None:
            return

        current_ssids = self._current_ssids()
        if self.all_updates_successful:
            self._remove_stale_ssid_entities(current_ssids)

        new_entities: list[Entity] = []
        for ssid in sorted(current_ssids):
            if ssid in self._entities_by_ssid:
                continue
            entity = OpenWrtUbusSsidPresenceBinarySensor(ssid)
            self._entities_by_ssid[ssid] = entity
            new_entities.append(entity)

        if new_entities:
            async_add_entities(new_entities)

    def _handle_coordinator_update(self) -> None:
        """Update entities after coordinator refresh."""
        self._sync_ssid_entities()
        for entity in self._entities_by_ssid.values():
            if entity.hass is not None:
                entity.async_write_ha_state()


def _get_manager(hass) -> OpenWrtUbusSsidPresenceManager | None:
    """Return global WiFi SSID presence manager when initialized."""
    domain_data = hass.data.get(DOMAIN)
    if not isinstance(domain_data, Mapping):
        return None
    manager = domain_data.get(_SSID_MANAGER_KEY)
    if isinstance(manager, OpenWrtUbusSsidPresenceManager):
        return manager
    return None


async def async_setup_entry(
    hass,
    entry: OpenWrtUbusWifiPresenceConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up global WiFi SSID presence binary sensors."""
    manager = _get_manager(hass)
    if manager is None:
        manager = OpenWrtUbusSsidPresenceManager(hass)
        hass.data.setdefault(DOMAIN, {})[_SSID_MANAGER_KEY] = manager

    await manager.async_register_entry(entry, async_add_entities)
