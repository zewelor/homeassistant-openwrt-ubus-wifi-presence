"""Constants for the OpenWrt Ubus WiFi Presence integration."""

from __future__ import annotations

from logging import Logger, getLogger

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME, CONF_VERIFY_SSL, Platform

LOGGER: Logger = getLogger(__package__)

DOMAIN = "openwrt_ubus"

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER]

CONF_ALIAS_MAPPING_FILE = "alias_mapping_file"
CONF_ALIAS_MAPPING_UI = "alias_mapping_ui"
CONF_ENDPOINT = "endpoint"
CONF_IP_ADDRESS = "ip_address"
CONF_MAPPING_SOURCE = "mapping_source"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_TRACKING_MODE = "tracking_mode"
CONF_USE_HTTPS = "use_https"
CONF_WIRELESS_SOFTWARE = "wireless_software"

WIRELESS_SOFTWARES: tuple[str, ...] = ("iwinfo", "hostapd")

DEFAULT_ALIAS_MAPPING_FILE = "openwrt_ubus_aliases.yaml"
DEFAULT_ALIAS_MAPPING_UI = ""
DEFAULT_ENDPOINT = "ubus"
DEFAULT_MAPPING_SOURCE = "hybrid"
DEFAULT_SCAN_INTERVAL = 30
DEFAULT_TRACKING_MODE = "known_or_alias"
DEFAULT_USE_HTTPS = False
DEFAULT_WIRELESS_SOFTWARE = "iwinfo"

TRACKING_MODES: tuple[str, ...] = ("known_or_alias", "all")
MAPPING_SOURCES: tuple[str, ...] = ("file", "ui", "hybrid")

MIN_SCAN_INTERVAL = 10
MAX_SCAN_INTERVAL = 300

DEFAULT_HTTP_PORT = 80
DEFAULT_HTTPS_PORT = 443

SENSITIVE_CONFIG_KEYS = {
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_IP_ADDRESS,
    CONF_HOST,
    CONF_PORT,
    CONF_VERIFY_SSL,
}

SENSITIVE_DIAGNOSTIC_KEYS = SENSITIVE_CONFIG_KEYS | {
    CONF_ALIAS_MAPPING_UI,
    "mac",
    "mapped_mac",
    "hostname",
    "ip_address",
}


def build_ubus_url(
    host: str,
    use_https: bool,
    ip_address: str | None,
    port: int | None,
    endpoint: str,
) -> str:
    """Build the ubus RPC URL for OpenWrt."""
    scheme = "https" if use_https else "http"
    target = ip_address or host

    if port is None:
        host_port = target
    else:
        default_port = DEFAULT_HTTPS_PORT if use_https else DEFAULT_HTTP_PORT
        host_port = target if port == default_port else f"{target}:{port}"

    clean_endpoint = endpoint.strip("/") or DEFAULT_ENDPOINT
    return f"{scheme}://{host_port}/{clean_endpoint}"
