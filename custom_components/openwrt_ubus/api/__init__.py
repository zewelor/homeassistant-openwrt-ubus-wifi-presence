"""API package for OpenWrt Ubus WiFi Presence."""

from .client import (
    OpenWrtUbusAuthenticationError,
    OpenWrtUbusClient,
    OpenWrtUbusClientError,
    OpenWrtUbusCommunicationError,
    OpenWrtUbusNoWifiAccessPointError,
)

__all__ = [
    "OpenWrtUbusAuthenticationError",
    "OpenWrtUbusClient",
    "OpenWrtUbusClientError",
    "OpenWrtUbusCommunicationError",
    "OpenWrtUbusNoWifiAccessPointError",
]
