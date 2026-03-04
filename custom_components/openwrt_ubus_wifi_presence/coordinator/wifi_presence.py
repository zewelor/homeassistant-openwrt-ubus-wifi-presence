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
    CONF_DHCP_SOFTWARE,
    CONF_SCAN_INTERVAL,
    CONF_WIRELESS_SOFTWARE,
    DEFAULT_DHCP_SOFTWARE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WIRELESS_SOFTWARE,
    DOMAIN,
    LOGGER,
)
from custom_components.openwrt_ubus.data import OpenWrtUbusWifiPresenceConfigEntry, WifiPresenceDevice
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

    async def _async_update_data(self) -> dict[str, WifiPresenceDevice]:
        """Fetch WiFi stations from configured backend."""
        backend = str(
            self.entry.options.get(
                CONF_WIRELESS_SOFTWARE,
                self.entry.data.get(CONF_WIRELESS_SOFTWARE, DEFAULT_WIRELESS_SOFTWARE),
            )
        )
        dhcp_software = str(
            self.entry.options.get(
                CONF_DHCP_SOFTWARE,
                self.entry.data.get(CONF_DHCP_SOFTWARE, DEFAULT_DHCP_SOFTWARE),
            )
        )

        try:
            dhcp_mapping = await self.client.get_dhcp_mapping(dhcp_software)
            interface_to_ssid = await self.client.get_interface_to_ssid_mapping()

            if backend == "hostapd":
                return await self._fetch_hostapd_clients(dhcp_mapping, interface_to_ssid)

            return await self._fetch_iwinfo_clients(dhcp_mapping, interface_to_ssid)
        except OpenWrtUbusAuthenticationError as err:
            raise UpdateFailed(f"Authentication error: {err}") from err
        except OpenWrtUbusCommunicationError as err:
            raise UpdateFailed(f"Communication error: {err}") from err
        except OpenWrtUbusClientError as err:
            raise UpdateFailed(f"OpenWrt ubus error: {err}") from err

    async def _fetch_iwinfo_clients(
        self,
        dhcp_mapping: dict[str, tuple[str | None, str | None]],
        interface_to_ssid: dict[str, str],
    ) -> dict[str, WifiPresenceDevice]:
        """Fetch WiFi clients via iwinfo backend."""
        devices: dict[str, WifiPresenceDevice] = {}
        ap_devices = await self.client.get_iwinfo_ap_devices()

        for ap_device in ap_devices:
            stations = await self.client.get_iwinfo_assoclist(ap_device)
            ssid = interface_to_ssid.get(ap_device)

            for station in stations:
                mac_raw = station.get("mac")
                if not isinstance(mac_raw, str):
                    continue
                mac = self.client.normalize_mac(mac_raw)
                if mac is None:
                    continue

                hostname, ip_address = dhcp_mapping.get(mac, (None, None))
                devices[mac] = WifiPresenceDevice(
                    mac=mac,
                    hostname=hostname,
                    ip_address=ip_address,
                    ap_device=ap_device,
                    ssid=ssid,
                    connected=True,
                )

        return devices

    async def _fetch_hostapd_clients(
        self,
        dhcp_mapping: dict[str, tuple[str | None, str | None]],
        interface_to_ssid: dict[str, str],
    ) -> dict[str, WifiPresenceDevice]:
        """Fetch WiFi clients via hostapd backend."""
        devices: dict[str, WifiPresenceDevice] = {}
        hostapd_interfaces = await self.client.get_hostapd_interfaces()

        for interface in hostapd_interfaces:
            clients = await self.client.get_hostapd_clients(interface)
            ssid = interface_to_ssid.get(interface.removeprefix("hostapd."), interface_to_ssid.get(interface))

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
