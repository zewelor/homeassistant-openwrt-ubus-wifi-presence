"""Device tracker entity for OpenWrt Ubus WiFi Presence."""

from __future__ import annotations

from custom_components.openwrt_ubus_wifi_presence.const import CONF_HOST
from custom_components.openwrt_ubus_wifi_presence.data import OpenWrtUbusWifiPresenceConfigEntry, WifiPresenceDevice
from custom_components.openwrt_ubus_wifi_presence.entity import OpenWrtUbusWifiPresenceEntity
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.device_tracker.const import SourceType


class OpenWrtUbusWifiPresenceDeviceTracker(ScannerEntity, OpenWrtUbusWifiPresenceEntity):
    """Represents one WiFi client presence tracker."""

    _attr_source_type = SourceType.ROUTER

    def __init__(
        self,
        coordinator,
        entry: OpenWrtUbusWifiPresenceConfigEntry,
        mac: str,
    ) -> None:
        """Initialize tracker entity for one client MAC on one router host."""
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
        """Return display name derived from hostname, IP, or MAC."""
        device = self._device
        if device and device.hostname:
            return device.hostname
        if device and device.ip_address:
            return device.ip_address.replace(".", "_")
        return self._mac.replace(":", "")

    @property
    def is_connected(self) -> bool:
        """Return whether the client is currently connected."""
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
    def mac_address(self) -> str:
        """Return normalized MAC address used by scanner registry logic."""
        return self._mac

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Return auxiliary metadata for troubleshooting and UI context."""
        device = self._device
        return {
            "router": self._host,
            "mac": self._mac,
            "hostname": device.hostname if device else None,
            "ip_address": device.ip_address if device else None,
            "ssid": device.ssid if device else None,
            "ap_device": device.ap_device if device else None,
        }
