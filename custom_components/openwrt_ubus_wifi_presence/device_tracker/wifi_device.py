"""Device tracker entity for OpenWrt Ubus WiFi Presence."""

from __future__ import annotations

from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.device_tracker.const import SourceType

from ..const import CONF_HOST
from ..data import OpenWrtUbusWifiPresenceConfigEntry, WifiPresenceDevice
from ..entity import OpenWrtUbusWifiPresenceEntity


class OpenWrtUbusWifiPresenceDeviceTracker(ScannerEntity, OpenWrtUbusWifiPresenceEntity):
    """Represents one WiFi client presence tracker."""

    _attr_source_type = SourceType.ROUTER

    def __init__(
        self,
        coordinator,
        entry: OpenWrtUbusWifiPresenceConfigEntry,
        mac: str,
    ) -> None:
        super().__init__(coordinator, entry)
        self._host = entry.data[CONF_HOST]
        self._mac = mac.upper()
        self._unique_id = f"{self._host}_{self._mac}"
        self._attr_unique_id = self._unique_id
        self._attr_entity_registry_enabled_default = True
        self._attr_mac_address = self._mac

    @property
    def _device(self) -> WifiPresenceDevice | None:
        return self.coordinator.data.get(self._mac)

    @property
    def name(self) -> str:
        device = self._device
        if device and device.hostname:
            return device.hostname
        if device and device.ip_address:
            return device.ip_address.replace(".", "_")
        return self._mac.replace(":", "")

    @property
    def is_connected(self) -> bool:
        device = self._device
        return bool(device and device.connected)

    @property
    def ip_address(self) -> str | None:
        device = self._device
        return device.ip_address if device else None

    @property
    def hostname(self) -> str | None:
        device = self._device
        return device.hostname if device else None

    @property
    def mac_address(self) -> str:
        return self._mac

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        device = self._device
        return {
            "router": self._host,
            "mac": self._mac,
            "hostname": device.hostname if device else None,
            "ip_address": device.ip_address if device else None,
            "ssid": device.ssid if device else None,
            "ap_device": device.ap_device if device else None,
        }
