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
        """Execute ubus `call` RPC operation with automatic session refresh retry."""
        try:
            response = await self._rpc_request(
                method="call",
                params=[self._session_id, subsystem, method, dict(params or {})],
            )
            return self._parse_call_response(response, subsystem=subsystem, rpc_method=method)
        except OpenWrtUbusAuthenticationError:
            # Session might have been lost or invalidated on OpenWrt (e.g. router reboot).
            # Force session reset, reconnect, and retry call once.
            self._session_id = self._EMPTY_SESSION
            self._session_expires_at = datetime.min.replace(tzinfo=UTC)

            response = await self._rpc_request(
                method="call",
                params=[self._session_id, subsystem, method, dict(params or {})],
            )
            return self._parse_call_response(response, subsystem=subsystem, rpc_method=method)

    async def get_wifi_ssid_inventory(self) -> tuple[dict[str, str], set[str], bool]:
        """Return interface mapping, WiFi SSIDs, and whether the inventory is complete."""
        mapping: dict[str, str] = {}
        configured_ssids: set[str] = set()
        wireless_statuses, complete = await self._get_wireless_status_payloads()

        for wireless_status in wireless_statuses:
            for radio_data in wireless_status.values():
                if not isinstance(radio_data, Mapping):
                    complete = False
                    continue

                interfaces = radio_data.get("interfaces")
                if not isinstance(interfaces, list):
                    complete = False
                    continue

                for interface in interfaces:
                    if not isinstance(interface, Mapping):
                        complete = False
                        continue

                    config = interface.get("config")
                    if not isinstance(config, Mapping):
                        complete = False
                        continue

                    ssid = config.get("ssid")
                    if not isinstance(ssid, str) or not (ssid := ssid.strip()):
                        continue
                    configured_ssids.add(ssid)

                    ifname = interface.get("ifname")
                    if isinstance(ifname, str) and ifname:
                        mapping[ifname] = ssid

        return mapping, configured_ssids, complete

    async def _get_wireless_status_payloads(self) -> tuple[list[dict[str, Any]], bool]:
        """Fetch wireless status payloads and report whether the inventory is complete."""
        if self._wireless_status_requires_device is False:
            try:
                return [await self.call("network.wireless", "status", {})], True
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
                return [payload], True

        try:
            wireless_devices = await self._get_wireless_devices()
        except OpenWrtUbusClientError:
            return [], False

        payloads: list[dict[str, Any]] = []
        complete = True
        for device in wireless_devices:
            try:
                payload = await self.call("network.wireless", "status", {"device": device})
            except OpenWrtUbusRpcCallError:
                complete = False
                continue
            if not payload:
                complete = False
            payloads.append(payload)
        return payloads, complete

    async def _get_wireless_devices(self) -> list[str]:
        """Return wireless device section names from UCI."""
        result = await self.call("uci", "get", {"config": "wireless"})
        values = result.get("values")
        if not isinstance(values, Mapping):
            raise OpenWrtUbusCommunicationError("Invalid UCI wireless configuration payload")

        devices: list[str] = []
        for section in values.values():
            if not isinstance(section, Mapping):
                raise OpenWrtUbusCommunicationError("Invalid UCI wireless section payload")

            if section.get(".type") != "wifi-device":
                continue
            section_name = section.get(".name")
            if not isinstance(section_name, str) or not section_name:
                raise OpenWrtUbusCommunicationError("Invalid UCI wireless device name")
            devices.append(section_name)
        return devices

    async def get_iwinfo_ap_devices(self) -> list[str]:
        """Get wireless interface list from iwinfo."""
        result = await self.call("iwinfo", "devices", {})
        devices = result.get("devices")
        if not isinstance(devices, list):
            raise OpenWrtUbusCommunicationError("Invalid iwinfo devices payload")
        if not all(isinstance(device, str) and device for device in devices):
            raise OpenWrtUbusCommunicationError("Invalid iwinfo device name")
        return devices

    async def get_iwinfo_assoclist(self, interface: str) -> list[dict[str, Any]]:
        """Get associated stations for one iwinfo interface."""
        result = await self.call("iwinfo", "assoclist", {"device": interface})
        results = result.get("results")
        if not isinstance(results, list):
            raise OpenWrtUbusCommunicationError("Invalid iwinfo association list payload")
        if not all(isinstance(item, dict) for item in results):
            raise OpenWrtUbusCommunicationError("Invalid iwinfo association entry")
        return results

    async def get_iwinfo_ssid(self, interface: str) -> str | None:
        """Get WiFi SSID for one iwinfo interface."""
        result = await self.call("iwinfo", "info", {"device": interface})
        ssid = result.get("ssid")
        if ssid is None:
            return None
        if not isinstance(ssid, str):
            raise OpenWrtUbusCommunicationError(f"Invalid iwinfo info payload for {interface}")
        normalized_ssid = ssid.strip()
        return normalized_ssid or None

    @staticmethod
    def normalize_mac(mac: str) -> str | None:
        """Normalize MAC address to uppercase colon-separated form."""
        if not isinstance(mac, str):
            return None

        stripped = mac.replace("-", "").replace(":", "").strip().upper()
        if len(stripped) != 12 or any(character not in "0123456789ABCDEF" for character in stripped):
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
