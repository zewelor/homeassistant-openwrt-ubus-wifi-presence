"""Coordinator used to poll WiFi station presence from OpenWrt ubus."""

from __future__ import annotations

from datetime import timedelta
import math
from typing import Any

from custom_components.openwrt_ubus.api import (
    OpenWrtUbusAuthenticationError,
    OpenWrtUbusClient,
    OpenWrtUbusClientError,
    OpenWrtUbusCommunicationError,
)
from custom_components.openwrt_ubus.const import (
    CONF_ALIAS_MAPPING_UI,
    CONF_MAPPING_SOURCE,
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
from homeassistant.helpers.update_coordinator import TimestampDataUpdateCoordinator, UpdateFailed


class OpenWrtUbusWifiPresenceCoordinator(TimestampDataUpdateCoordinator[dict[str, WifiPresenceDevice]]):
    """Coordinator that tracks only WiFi client presence."""

    def __init__(
        self,
        *,
        hass,
        entry: OpenWrtUbusWifiPresenceConfigEntry,
        client: OpenWrtUbusClient,
    ) -> None:
        """Initialize coordinator with the fixed update interval and ubus client."""
        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            config_entry=entry,
        )
        self.entry = entry
        self.client = client
        self._alias_loader = AliasMappingLoader(hass=hass, entry=entry, normalize_mac=client.normalize_mac)
        self._alias_entries: dict[str, AliasMappingEntry] = {}
        self._known_macs: dict[str, str | None] = {}
        self._known_ssids: set[str] = set()
        self._ssid_inventory_complete = False
        self._tracker_targets: dict[str, TrackerTarget] = {}

    @property
    def tracker_targets(self) -> dict[str, TrackerTarget]:
        """Return tracker targets computed for the current mode."""
        return self._tracker_targets

    @property
    def known_ssids(self) -> set[str]:
        """Return WiFi SSIDs discovered even with zero connected clients."""
        return self._known_ssids

    @property
    def ssid_inventory_complete(self) -> bool:
        """Return whether the latest WiFi SSID inventory was complete."""
        return self._ssid_inventory_complete

    @property
    def tracking_mode(self) -> str:
        """Return active tracking mode for this entry."""
        mode = str(self.entry.options.get(CONF_TRACKING_MODE, DEFAULT_TRACKING_MODE)).strip()
        return mode if mode in TRACKING_MODES else DEFAULT_TRACKING_MODE

    @property
    def alias_mapping_file(self) -> str:
        """Return configured alias mapping file path."""
        return self._alias_loader.mapping_file

    @property
    def mapping_source(self) -> str:
        """Return active alias mapping source mode."""
        mode = str(self.entry.options.get(CONF_MAPPING_SOURCE, DEFAULT_MAPPING_SOURCE)).strip()
        return mode if mode in MAPPING_SOURCES else DEFAULT_MAPPING_SOURCE

    @property
    def alias_mapping_ui(self) -> str:
        """Return configured UI alias mapping YAML."""
        raw_value = self.entry.options.get(CONF_ALIAS_MAPPING_UI, DEFAULT_ALIAS_MAPPING_UI)
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
            (
                interface_to_ssid,
                configured_ssids,
                configured_inventory_complete,
            ) = await self.client.get_wifi_ssid_inventory()
            devices, observed_ssids, observed_inventory_complete = await self._fetch_iwinfo_clients(interface_to_ssid)

        except OpenWrtUbusAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            ) from err
        except OpenWrtUbusCommunicationError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_failed",
            ) from err
        except OpenWrtUbusClientError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="unexpected_client_error",
            ) from err

        self._known_ssids = configured_ssids | observed_ssids
        self._ssid_inventory_complete = configured_inventory_complete and observed_inventory_complete
        self._known_macs = self._build_known_macs()
        self._tracker_targets = self._build_tracker_targets(devices)
        return devices

    async def _fetch_iwinfo_clients(
        self,
        interface_to_ssid: dict[str, str],
    ) -> tuple[dict[str, WifiPresenceDevice], set[str], bool]:
        """Fetch currently associated WiFi clients via iwinfo interfaces."""
        devices: dict[str, WifiPresenceDevice] = {}
        known_ssids = {ssid.strip() for ssid in interface_to_ssid.values() if ssid.strip()}
        inventory_complete = True
        ap_devices = await self.client.get_iwinfo_ap_devices()

        for ap_device in ap_devices:
            stations = await self.client.get_iwinfo_assoclist(ap_device)
            # Try interface_to_ssid mapping first, then fallback to iwinfo info
            ssid = interface_to_ssid.get(ap_device)
            if not ssid:
                ssid = await self.client.get_iwinfo_ssid(ap_device)
                if not ssid:
                    inventory_complete = False
            normalized_ssid = ssid.strip() if isinstance(ssid, str) else None
            if normalized_ssid:
                known_ssids.add(normalized_ssid)

            for station in stations:
                # Ignore stations explicitly reported as unauthorized.
                # Stations with failed WPA 4-way handshakes ("didn't respond") or incomplete auth
                # may briefly exist in kernel station lists, but lack network connectivity.
                if station.get("authorized") is False:
                    continue

                mac_raw = station.get("mac")
                if not isinstance(mac_raw, str):
                    continue
                mac = self.client.normalize_mac(mac_raw)
                if mac is None:
                    continue

                candidate = WifiPresenceDevice(
                    mac=mac,
                    ap_device=ap_device,
                    ssid=normalized_ssid,
                    inactive_ms=self._optional_station_int(station.get("inactive"), minimum=0),
                    signal_dbm=self._optional_station_int(station.get("signal")),
                )
                current = devices.get(mac)
                if current is None or self._association_sort_key(candidate) < self._association_sort_key(current):
                    devices[mac] = candidate

        return devices, known_ssids, inventory_complete

    @staticmethod
    def _optional_station_int(value: Any, *, minimum: int | None = None) -> int | None:
        """Return one finite numeric station metric as an integer."""
        if isinstance(value, bool) or not isinstance(value, int | float):
            return None
        if isinstance(value, float) and not math.isfinite(value):
            return None
        if minimum is not None and value < minimum:
            return None
        return int(value)

    @staticmethod
    def _association_sort_key(device: WifiPresenceDevice) -> tuple[float, float, str]:
        """Return deterministic preference key for duplicate associations."""
        inactive_ms = float(device.inactive_ms) if device.inactive_ms is not None else math.inf
        signal_preference = -float(device.signal_dbm) if device.signal_dbm is not None else math.inf
        return inactive_ms, signal_preference, device.ap_device

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
