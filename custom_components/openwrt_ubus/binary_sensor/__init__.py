"""Binary sensor platform for OpenWrt Ubus WiFi Presence."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from hashlib import sha1

from custom_components.openwrt_ubus.const import DOMAIN
from custom_components.openwrt_ubus.coordinator import OpenWrtUbusWifiPresenceCoordinator
from custom_components.openwrt_ubus.data import OpenWrtUbusWifiPresenceConfigEntry, WifiPresenceDevice
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

_SSID_MANAGER_KEY = "ssid_presence_manager"


def _normalize_ssid(ssid: str) -> str:
    """Normalize SSID values used as entity keys."""
    return ssid.strip()


class OpenWrtUbusSsidPresenceBinarySensor(BinarySensorEntity):
    """Binary sensor that is on when any client is connected to one SSID."""

    _attr_has_entity_name = True

    def __init__(self, ssid: str) -> None:
        """Initialize the SSID presence sensor."""
        self._ssid = ssid
        self._slug = slugify(ssid, separator="_")
        self._ssid_hash = sha1(ssid.encode(), usedforsecurity=False).hexdigest()[:12]
        self._attr_name = f"WiFi {ssid} Presence"
        self._attr_unique_id = f"openwrt_wifi_ssid_presence_{self._ssid_hash}"
        self._attr_suggested_object_id = f"openwrt_wifi_{self._slug}_presence"

    @property
    def ssid(self) -> str:
        """Return SSID represented by this sensor."""
        return self._ssid

    @property
    def is_on(self) -> bool:
        """Return true when at least one client is connected to this SSID."""
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
    """Manage global SSID presence sensors across all integration entries."""

    def __init__(self, hass) -> None:
        """Initialize manager."""
        self.hass = hass
        self._entities_by_ssid: dict[str, OpenWrtUbusSsidPresenceBinarySensor] = {}
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

    def _current_ssids(self) -> set[str]:
        """Return all configured or currently observed SSIDs."""
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
                if not device.connected or not isinstance(device.ssid, str):
                    continue
                ssid = _normalize_ssid(device.ssid)
                if ssid:
                    ssids.add(ssid)
        return ssids

    def connected_count_for_ssid(self, ssid: str) -> int:
        """Count unique connected clients for one SSID across all routers."""
        connected_macs: set[str] = set()
        for devices in self._iter_coordinator_data():
            for mac, device in devices.items():
                if not device.connected:
                    continue
                if not isinstance(device.ssid, str) or _normalize_ssid(device.ssid) != ssid:
                    continue
                connected_macs.add(mac)
        return len(connected_macs)

    def _sync_ssid_entities(self) -> None:
        """Create missing entities for newly discovered SSIDs."""
        if self._owner_entry_id is None:
            return
        async_add_entities = self._async_add_entities_by_entry.get(self._owner_entry_id)
        if async_add_entities is None:
            return

        new_entities: list[Entity] = []
        for ssid in sorted(self._current_ssids()):
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
    """Return global SSID presence manager when initialized."""
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
    """Set up global SSID presence binary sensors."""
    manager = _get_manager(hass)
    if manager is None:
        manager = OpenWrtUbusSsidPresenceManager(hass)
        hass.data.setdefault(DOMAIN, {})[_SSID_MANAGER_KEY] = manager

    await manager.async_register_entry(entry, async_add_entities)
