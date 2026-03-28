"""Coordinator used to poll WiFi station presence from OpenWrt ubus."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta

from custom_components.openwrt_ubus.api import (
    OpenWrtUbusAuthenticationError,
    OpenWrtUbusClient,
    OpenWrtUbusClientError,
    OpenWrtUbusCommunicationError,
)
from custom_components.openwrt_ubus.const import (
    CONF_ALIAS_MAPPING_UI,
    CONF_MAPPING_SOURCE,
    CONF_SCAN_INTERVAL,
    CONF_TRACKING_MODE,
    DEFAULT_ALIAS_MAPPING_UI,
    DEFAULT_MAPPING_SOURCE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TRACKING_MODE,
    DOMAIN,
    LOGGER,
    MAPPING_SOURCES,
    TRACKING_MODES,
)
from custom_components.openwrt_ubus.data import (
    OpenWrtUbusWifiPresenceConfigEntry,
    TrackerTarget,
    TrackerTargetSource,
    TrackerTargetType,
    WifiPresenceDevice,
)
from custom_components.openwrt_ubus.utils.alias_mapping import AliasMappingEntry, AliasMappingLoader
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed


class OpenWrtUbusWifiPresenceCoordinator(DataUpdateCoordinator[dict[str, WifiPresenceDevice]]):
    """Coordinator that tracks only WiFi client presence."""

    def __init__(
        self,
        *,
        hass,
        entry: OpenWrtUbusWifiPresenceConfigEntry,
        client: OpenWrtUbusClient,
    ) -> None:
        """Initialize coordinator with configured update interval and ubus client."""
        scan_interval = int(
            entry.options.get(CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        )
        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.entry = entry
        self.client = client
        self._alias_loader = AliasMappingLoader(hass=hass, entry=entry, normalize_mac=client.normalize_mac)
        self._alias_entries: dict[str, AliasMappingEntry] = {}
        self._known_macs: dict[str, str | None] = {}
        self._tracker_targets: dict[str, TrackerTarget] = {}

    @property
    def tracker_targets(self) -> dict[str, TrackerTarget]:
        """Return tracker targets computed for the current mode."""
        return self._tracker_targets

    @property
    def tracking_mode(self) -> str:
        """Return active tracking mode for this entry."""
        mode = str(self.entry.options.get(CONF_TRACKING_MODE, self.entry.data.get(CONF_TRACKING_MODE, ""))).strip()
        return mode if mode in TRACKING_MODES else DEFAULT_TRACKING_MODE

    @property
    def alias_mapping_file(self) -> str:
        """Return configured alias mapping file path."""
        return self._alias_loader.mapping_file

    @property
    def mapping_source(self) -> str:
        """Return active alias mapping source mode."""
        mode = str(self.entry.options.get(CONF_MAPPING_SOURCE, self.entry.data.get(CONF_MAPPING_SOURCE, ""))).strip()
        return mode if mode in MAPPING_SOURCES else DEFAULT_MAPPING_SOURCE

    @property
    def alias_mapping_ui(self) -> str:
        """Return configured UI alias mapping YAML."""
        raw_value = self.entry.options.get(
            CONF_ALIAS_MAPPING_UI,
            self.entry.data.get(CONF_ALIAS_MAPPING_UI, DEFAULT_ALIAS_MAPPING_UI),
        )
        if not isinstance(raw_value, str):
            return DEFAULT_ALIAS_MAPPING_UI
        return raw_value.strip()

    @property
    def alias_mapping_summary(self) -> dict[str, int]:
        """Return effective alias mapping summary by source."""
        return self._alias_loader.mapping_summary

    async def _async_update_data(self) -> dict[str, WifiPresenceDevice]:
        """Fetch WiFi stations via iwinfo."""
        try:
            self._alias_entries = await self._alias_loader.async_refresh()
            interface_to_ssid = await self.client.get_interface_to_ssid_mapping()
            devices = await self._fetch_iwinfo_clients(interface_to_ssid)

        except OpenWrtUbusAuthenticationError as err:
            raise ConfigEntryAuthFailed(f"Authentication error: {err}") from err
        except OpenWrtUbusCommunicationError as err:
            raise UpdateFailed(f"Communication error: {err}") from err
        except OpenWrtUbusClientError as err:
            raise UpdateFailed(f"OpenWrt ubus error: {err}") from err

        self._known_macs = self._build_known_macs()
        self._tracker_targets = self._build_tracker_targets(devices)
        return devices

    async def _fetch_iwinfo_clients(
        self,
        interface_to_ssid: dict[str, str],
    ) -> dict[str, WifiPresenceDevice]:
        """Fetch WiFi clients via iwinfo backend."""
        devices: dict[str, WifiPresenceDevice] = {}
        ap_devices = await self.client.get_iwinfo_ap_devices()

        for ap_device in ap_devices:
            stations = await self.client.get_iwinfo_assoclist(ap_device)
            # Try interface_to_ssid mapping first, then fallback to iwinfo info
            ssid = interface_to_ssid.get(ap_device)
            if not ssid:
                ssid = await self.client.get_iwinfo_ssid(ap_device)

            for station in stations:
                mac_raw = station.get("mac")
                if not isinstance(mac_raw, str):
                    continue
                mac = self.client.normalize_mac(mac_raw)
                if mac is None:
                    continue

                devices[mac] = WifiPresenceDevice(
                    mac=mac,
                    hostname=None,
                    ip_address=None,
                    ap_device=ap_device,
                    ssid=ssid,
                    connected=True,
                )

        return devices

    def _build_known_macs(self) -> dict[str, str | None]:
        """Build MAC->friendly name map from Home Assistant device registry."""
        registry = dr.async_get(self.hass)
        known_macs: dict[str, str | None] = {}
        for device_entry in registry.devices.values():
            display_name = device_entry.name_by_user or device_entry.name
            for connection_type, connection_value in device_entry.connections:
                if connection_type != dr.CONNECTION_NETWORK_MAC:
                    continue
                if not isinstance(connection_value, str) or not connection_value:
                    continue
                normalized_mac = self.client.normalize_mac(connection_value)
                if normalized_mac is None:
                    continue
                known_macs[normalized_mac] = display_name
        return known_macs

    def _build_tracker_targets(self, devices: dict[str, WifiPresenceDevice]) -> dict[str, TrackerTarget]:
        """Build tracker targets based on tracking mode, alias map, and known devices."""
        targets: dict[str, TrackerTarget] = {}
        aliased_macs: set[str] = set()

        for alias_slug, alias_entry in self._alias_entries.items():
            entity_key = f"alias_{alias_slug}"
            targets[entity_key] = TrackerTarget(
                entity_key=entity_key,
                tracker_type=TrackerTargetType.ALIAS,
                source=TrackerTargetSource.ALIAS,
                display_name=alias_entry.display_name,
                mac=alias_entry.mac,
            )
            aliased_macs.add(alias_entry.mac)

        mode = self.tracking_mode
        if mode == "known_or_alias":
            for mac, known_name in sorted(self._known_macs.items()):
                if mac in aliased_macs:
                    continue
                entity_key = f"mac_{mac}"
                targets[entity_key] = TrackerTarget(
                    entity_key=entity_key,
                    tracker_type=TrackerTargetType.MAC,
                    source=TrackerTargetSource.KNOWN,
                    display_name=known_name or mac.replace(":", ""),
                    mac=mac,
                )
            return targets

        for mac in sorted(devices.keys()):
            if mac in aliased_macs:
                continue

            known_name = self._known_macs.get(mac)
            if known_name:
                display_name = known_name
                source = TrackerTargetSource.KNOWN
            else:
                display_name = mac.replace(":", "")
                source = TrackerTargetSource.ALL

            entity_key = f"mac_{mac}"
            targets[entity_key] = TrackerTarget(
                entity_key=entity_key,
                tracker_type=TrackerTargetType.MAC,
                source=source,
                display_name=display_name,
                mac=mac,
            )

        return targets

    async def _fetch_hostapd_clients(
        self,
        interface_to_ssid: dict[str, str],
        dhcp_mapping: dict[str, tuple[str | None, str | None]],
    ) -> dict[str, WifiPresenceDevice]:
        """Fetch WiFi clients via hostapd backend."""
        devices: dict[str, WifiPresenceDevice] = {}
        hostapd_interfaces = await self.client.get_hostapd_interfaces()

        for interface in hostapd_interfaces:
            clients = await self.client.get_hostapd_clients(interface)
            raw_if = interface.removeprefix("hostapd.")
            ssid = interface_to_ssid.get(raw_if, interface_to_ssid.get(interface))

            for mac_raw, client_data in clients.items():
                if not isinstance(client_data, Mapping):
                    continue

                if client_data.get("authorized") is False:
                    continue

                mac = self.client.normalize_mac(mac_raw)
                if mac is None:
                    continue

                hostname, ip_address = dhcp_mapping.get(mac, (None, None))
                devices[mac] = WifiPresenceDevice(
                    mac=mac,
                    hostname=hostname,
                    ip_address=ip_address,
                    ap_device=interface,
                    ssid=ssid,
                    connected=True,
                )

        return devices
