"""Device tracker entity for OpenWrt Ubus WiFi Presence."""

from __future__ import annotations

from custom_components.openwrt_ubus.const import CONF_HOST, DOMAIN
from custom_components.openwrt_ubus.data import (
    OpenWrtUbusWifiPresenceConfigEntry,
    TrackerTarget,
    TrackerTargetType,
    WifiPresenceDevice,
)
from custom_components.openwrt_ubus.entity import OpenWrtUbusWifiPresenceEntity
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.device_tracker.const import SourceType
from homeassistant.config_entries import ConfigEntryState
from homeassistant.util import slugify


class OpenWrtUbusWifiPresenceDeviceTracker(ScannerEntity, OpenWrtUbusWifiPresenceEntity):
    """Represents one WiFi client tracker target."""

    _attr_source_type = SourceType.ROUTER

    def __init__(
        self,
        coordinator,
        entry: OpenWrtUbusWifiPresenceConfigEntry,
        entity_key: str,
    ) -> None:
        """Initialize tracker entity for one alias/MAC target."""
        super().__init__(coordinator)
        self._host = entry.data[CONF_HOST]
        self._entity_key = entity_key
        self._fallback_name = entity_key
        self._fallback_mac = self._extract_mac_from_entity_key(entity_key)
        self._unique_id = f"{self._host}_{self._entity_key}"
        self._attr_unique_id = self._unique_id
        self._attr_suggested_object_id = self._build_suggested_object_id(entity_key)
        self._attr_entity_registry_enabled_default = True

    @property
    def _target(self) -> TrackerTarget | None:
        return self.coordinator.tracker_targets.get(self._entity_key)

    @staticmethod
    def _extract_mac_from_entity_key(entity_key: str) -> str | None:
        """Extract MAC from mac_* tracker keys."""
        if entity_key.startswith("mac_"):
            return entity_key.removeprefix("mac_")
        return None

    @staticmethod
    def _build_suggested_object_id(entity_key: str) -> str:
        """Build suggested object id for stable entity naming."""
        if entity_key.startswith("alias_"):
            return entity_key.removeprefix("alias_")
        if entity_key.startswith("mac_"):
            mac = entity_key.removeprefix("mac_").replace(":", "").lower()
            return f"mac_{mac}"
        return slugify(entity_key, separator="_")

    @property
    def _resolved_mac(self) -> str | None:
        """Resolve current target MAC."""
        target = self._target
        if target and target.mac:
            return target.mac
        return self._fallback_mac

    def _find_device_global(self) -> tuple[WifiPresenceDevice | None, str | None]:
        """Find device across all OpenWrt router coordinators.

        Returns tuple of (device, router_host) or (None, None) if not found.
        """
        mac = self._resolved_mac
        if mac is None:
            return None, None

        # Check local coordinator first
        device = self.coordinator.data.get(mac)
        if device:
            return device, self._host

        # Check all other OpenWrt coordinators
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.state != ConfigEntryState.LOADED:
                continue
            if entry.entry_id == self.coordinator.entry.entry_id:
                continue

            runtime_data = getattr(entry, "runtime_data", None)
            if runtime_data is None:
                continue
            coordinator = getattr(runtime_data, "coordinator", None)
            if coordinator is None:
                continue

            device = coordinator.data.get(mac)
            if device:
                host = entry.data.get(CONF_HOST, "unknown")
                return device, host

        return None, None

    @property
    def _device(self) -> WifiPresenceDevice | None:
        """Return device from any router coordinator."""
        device, _ = self._find_device_global()
        return device

    @property
    def name(self) -> str:
        """Return display name for this tracker target."""
        target = self._target
        if target:
            self._fallback_name = target.display_name
            return target.display_name
        return self._fallback_name

    @property
    def is_connected(self) -> bool:
        """Return whether current target MAC is currently connected."""
        device = self._device
        return bool(device and device.connected)

    @property
    def ip_address(self) -> str | None:
        """Return current IPv4 address when available."""
        device = self._device
        return device.ip_address if device else None

    @property
    def hostname(self) -> str | None:
        """Return DHCP hostname when available."""
        device = self._device
        return device.hostname if device else None

    @property
    def mac_address(self) -> str | None:
        """Return MAC address for HA device_tracker entity merging.

        When the same MAC is tracked on multiple OpenWrt routers,
        returning the MAC allows HA to merge them into a single entity.
        The entity shows home when connected to any router.
        """
        return self._resolved_mac

    @property
    def extra_state_attributes(self) -> dict[str, str | bool | None]:
        """Return auxiliary metadata for troubleshooting and UI context."""
        device, router = self._find_device_global()
        target = self._target
        target_type = target.tracker_type if target else TrackerTargetType.MAC
        target_source = target.source.value if target else None
        mapped_mac = target.mac if target else self._fallback_mac

        return {
            "router": router or self._host,
            "entity_key": self._entity_key,
            "tracker_type": target_type.value,
            "target_source": target_source,
            "mapped_mac": mapped_mac,
            "mapping_exists": target is not None,
            "ssid": device.ssid if device else None,
            "ap_device": device.ap_device if device else None,
        }
