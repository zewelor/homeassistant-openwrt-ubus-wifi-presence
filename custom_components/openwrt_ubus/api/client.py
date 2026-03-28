"""Ubus API client for OpenWrt WiFi presence tracking."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Any

from aiohttp import ClientError, ClientSession


class OpenWrtUbusClientError(RuntimeError):
    """Base OpenWrt Ubus client error."""


class OpenWrtUbusCommunicationError(OpenWrtUbusClientError):
    """Raised for transport or protocol issues."""


class OpenWrtUbusRpcCallError(OpenWrtUbusCommunicationError):
    """Raised when ubus `call` returns a non-zero status code."""

    def __init__(self, *, code: int, subsystem: str, rpc_method: str) -> None:
        """Store ubus call metadata for compatibility fallbacks."""
        self.code = code
        self.subsystem = subsystem
        self.rpc_method = rpc_method
        super().__init__(f"OpenWrt ubus returned error code {code} for {subsystem}.{rpc_method}")


class OpenWrtUbusAuthenticationError(OpenWrtUbusClientError):
    """Raised for authentication/authorization errors."""


class OpenWrtUbusClient:
    """Minimal ubus JSON-RPC client focused on WiFi presence tracking."""

    _EMPTY_SESSION = "00000000000000000000000000000000"

    def __init__(
        self,
        *,
        session: ClientSession,
        url: str,
        host: str,
        username: str,
        password: str,
        verify_ssl: bool,
        timeout_seconds: int = 15,
    ) -> None:
        """Initialize ubus client connection parameters."""
        self._session = session
        self._url = url
        self._host = host
        self._username = username
        self._password = password
        self._verify_ssl = verify_ssl
        self._timeout = timeout_seconds
        self._session_id = self._EMPTY_SESSION
        self._session_expires_at = datetime.min.replace(tzinfo=UTC)
        self._wireless_status_requires_device: bool | None = None

    async def connect(self) -> str:
        """Authenticate against ubus and return session id."""
        response = await self._rpc_request(
            method="call",
            params=[
                self._EMPTY_SESSION,
                "session",
                "login",
                {"username": self._username, "password": self._password},
            ],
            ensure_session=False,
        )
        payload = self._parse_call_response(response, subsystem="session", rpc_method="login")

        session_id = payload.get("ubus_rpc_session")
        if not isinstance(session_id, str) or len(session_id) < 8:
            raise OpenWrtUbusAuthenticationError("Invalid ubus session id in login response")

        expires_seconds = payload.get("expires", 300)
        if not isinstance(expires_seconds, int):
            expires_seconds = 300

        self._session_id = session_id
        self._session_expires_at = datetime.now(tz=UTC) + timedelta(seconds=max(30, expires_seconds - 10))
        return session_id

    async def close(self) -> None:
        """Destroy remote ubus session."""
        if self._session_id == self._EMPTY_SESSION:
            return

        with suppress(OpenWrtUbusClientError):
            await self.call("session", "destroy", {})

        self._session_id = self._EMPTY_SESSION
        self._session_expires_at = datetime.min.replace(tzinfo=UTC)

    async def call(self, subsystem: str, method: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Execute ubus `call` RPC operation."""
        response = await self._rpc_request(
            method="call",
            params=[self._session_id, subsystem, method, dict(params or {})],
        )
        return self._parse_call_response(response, subsystem=subsystem, rpc_method=method)

    async def list(self, pattern: str = "*") -> dict[str, Any]:
        """Execute ubus `list` RPC operation."""
        response = await self._rpc_request(method="list", params=[self._session_id, pattern])
        result = response.get("result")
        if not isinstance(result, dict):
            raise OpenWrtUbusCommunicationError(f"Invalid list response payload for pattern '{pattern}'")
        return result

    async def get_interface_to_ssid_mapping(self) -> dict[str, str]:
        """Map interface names (ifname) to SSID."""
        mapping: dict[str, str] = {}
        wireless_statuses = await self._get_wireless_status_payloads()

        for wireless_status in wireless_statuses:
            for radio_data in wireless_status.values():
                if not isinstance(radio_data, Mapping):
                    continue

                interfaces = radio_data.get("interfaces", [])
                if not isinstance(interfaces, list):
                    continue

                for interface in interfaces:
                    if not isinstance(interface, Mapping):
                        continue
                    ifname = interface.get("ifname")
                    config = interface.get("config", {})
                    if not isinstance(config, Mapping):
                        continue
                    ssid = config.get("ssid")

                    if isinstance(ifname, str) and isinstance(ssid, str) and ssid:
                        mapping[ifname] = ssid

        return mapping

    async def _get_wireless_status_payloads(self) -> list[dict[str, Any]]:
        """Fetch wireless status using a capability-based fallback."""
        if self._wireless_status_requires_device is False:
            try:
                return [await self.call("network.wireless", "status", {})]
            except OpenWrtUbusRpcCallError as err:
                if err.code != 2 or err.subsystem != "network.wireless" or err.rpc_method != "status":
                    raise
                self._wireless_status_requires_device = True

        if self._wireless_status_requires_device is None:
            try:
                payload = await self.call("network.wireless", "status", {})
            except OpenWrtUbusRpcCallError as err:
                if err.code != 2 or err.subsystem != "network.wireless" or err.rpc_method != "status":
                    raise
                self._wireless_status_requires_device = True
            else:
                self._wireless_status_requires_device = False
                return [payload]

        try:
            wireless_devices = await self._get_wireless_devices()
        except OpenWrtUbusClientError:
            return []

        payloads: list[dict[str, Any]] = []
        for device in wireless_devices:
            try:
                payloads.append(await self.call("network.wireless", "status", {"device": device}))
            except OpenWrtUbusRpcCallError:
                continue
        return payloads

    async def _get_wireless_devices(self) -> list[str]:
        """Return wireless device section names from UCI."""
        result = await self.call("uci", "get", {"config": "wireless"})
        values = result.get("values")
        if not isinstance(values, Mapping):
            return []

        devices: list[str] = []
        for section in values.values():
            if not isinstance(section, Mapping):
                continue

            section_type = section.get(".type")
            section_name = section.get(".name")
            if section_type != "wifi-device" or not isinstance(section_name, str) or not section_name:
                continue

            devices.append(section_name)

        return devices

    async def get_iwinfo_ap_devices(self) -> list[str]:
        """Get wireless interface list from iwinfo."""
        result = await self.call("iwinfo", "devices", {})
        devices = result.get("devices")
        if not isinstance(devices, list):
            return []
        return [device for device in devices if isinstance(device, str)]

    async def get_iwinfo_assoclist(self, interface: str) -> list[dict[str, Any]]:
        """Get associated stations for one iwinfo interface."""
        result = await self.call("iwinfo", "assoclist", {"device": interface})
        if isinstance(result, list):
            return [item for item in result if isinstance(item, dict)]

        results = result.get("results")
        if isinstance(results, list):
            return [item for item in results if isinstance(item, dict)]

        return []

    async def get_hostapd_interfaces(self) -> list[str]:
        """Get hostapd interface object names exposed via ubus."""
        result = await self.list("hostapd.*")
        return [name for name in result if isinstance(name, str) and name.startswith("hostapd.")]

    async def get_hostapd_clients(self, interface: str) -> dict[str, Any]:
        """Get connected clients for hostapd ubus object."""
        result = await self.call(interface, "get_clients", {})
        clients = result.get("clients")
        if isinstance(clients, dict):
            return clients
        return {}

    async def get_dhcp_leases(self) -> dict[str, tuple[str | None, str | None]]:
        """Get DHCP leases mapped by MAC address.

        Returns dict mapping MAC -> (hostname, ip_address).
        """
        result = await self.call("luci-rpc", "getDHCPLeases", {})
        leases = result.get("dhcp_leases", [])
        if not isinstance(leases, list):
            return {}

        mapping: dict[str, tuple[str | None, str | None]] = {}
        for lease in leases:
            if not isinstance(lease, dict):
                continue
            mac_raw = lease.get("mac")
            if not isinstance(mac_raw, str):
                continue
            mac = self.normalize_mac(mac_raw)
            if mac is None:
                continue

            hostname = lease.get("hostname")
            ip = lease.get("ip")
            mapping[mac] = (
                hostname if isinstance(hostname, str) else None,
                ip if isinstance(ip, str) else None,
            )

        return mapping

    @staticmethod
    def normalize_mac(mac: str) -> str | None:
        """Normalize MAC address to uppercase colon-separated form."""
        if not isinstance(mac, str):
            return None

        stripped = mac.replace("-", "").replace(":", "").strip().upper()
        if len(stripped) != 12:
            return None

        return ":".join(stripped[index : index + 2] for index in range(0, 12, 2))

    async def _ensure_connected(self) -> None:
        """Ensure current ubus session is valid."""
        if self._session_id == self._EMPTY_SESSION or datetime.now(tz=UTC) >= self._session_expires_at:
            await self.connect()

    async def _rpc_request(self, method: str, params: list[Any], ensure_session: bool = True) -> dict[str, Any]:
        """Execute low-level JSON-RPC request against ubus endpoint."""
        if ensure_session:
            await self._ensure_connected()
            # Update session_id in params after connecting (params[0] is always the session_id for call/list)
            if params and isinstance(params, list):
                params[0] = self._session_id

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }

        try:
            async with asyncio.timeout(self._timeout):
                response = await self._session.post(
                    self._url,
                    json=payload,
                    ssl=self._verify_ssl,
                )
        except (TimeoutError, ClientError) as err:
            raise OpenWrtUbusCommunicationError(f"Cannot reach OpenWrt ubus endpoint on {self._host}") from err

        if response.status != 200:
            raise OpenWrtUbusCommunicationError(f"OpenWrt ubus endpoint returned HTTP status {response.status}")

        try:
            body = await response.json()
        except ValueError as err:
            raise OpenWrtUbusCommunicationError("OpenWrt ubus returned invalid JSON") from err

        if not isinstance(body, dict):
            raise OpenWrtUbusCommunicationError("OpenWrt ubus returned unexpected JSON payload")

        if "error" in body:
            error_obj = body["error"]
            if isinstance(error_obj, Mapping):
                code = error_obj.get("code")
                message = error_obj.get("message", "Unknown RPC error")
                if code in (-32002, 6):
                    raise OpenWrtUbusAuthenticationError(str(message))
                raise OpenWrtUbusCommunicationError(str(message))
            raise OpenWrtUbusCommunicationError("OpenWrt ubus returned generic RPC error")

        return body

    def _parse_call_response(self, response: dict[str, Any], subsystem: str, rpc_method: str) -> dict[str, Any]:
        """Validate and parse ubus `call` response payload."""
        result = response.get("result")
        if not isinstance(result, list) or not result:
            raise OpenWrtUbusCommunicationError(
                f"Invalid ubus response for {subsystem}.{rpc_method}: missing result list"
            )

        code = result[0]
        if code != 0:
            if code == 6:
                raise OpenWrtUbusAuthenticationError(f"Permission denied for {subsystem}.{rpc_method}")
            raise OpenWrtUbusRpcCallError(code=code, subsystem=subsystem, rpc_method=rpc_method)

        if len(result) == 1:
            return {}

        payload = result[1]
        if not isinstance(payload, dict):
            raise OpenWrtUbusCommunicationError(f"Invalid ubus payload for {subsystem}.{rpc_method}: expected dict")

        return payload
