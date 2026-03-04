"""Alias mapping loader for OpenWrt WiFi presence tracking."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from custom_components.openwrt_ubus.const import CONF_ALIAS_MAPPING_FILE, DEFAULT_ALIAS_MAPPING_FILE, LOGGER
from homeassistant.core import HomeAssistant
from homeassistant.util import slugify

if TYPE_CHECKING:
    from collections.abc import Callable

    from custom_components.openwrt_ubus.data import OpenWrtUbusWifiPresenceConfigEntry


@dataclass(slots=True, frozen=True)
class AliasMappingEntry:
    """Normalized alias mapping entry."""

    alias: str
    slug: str
    mac: str


class AliasMappingLoader:
    """Load and cache alias->MAC mapping from a YAML file."""

    def __init__(
        self,
        *,
        hass: HomeAssistant,
        entry: OpenWrtUbusWifiPresenceConfigEntry,
        normalize_mac: Callable[[str], str | None],
    ) -> None:
        """Initialize the alias mapping loader."""
        self._hass = hass
        self._entry = entry
        self._normalize_mac = normalize_mac
        self._last_mtime_ns: int | None = None
        self._last_path: Path | None = None
        self._entries: dict[str, AliasMappingEntry] = {}

    @property
    def mapping(self) -> dict[str, AliasMappingEntry]:
        """Return current mapping keyed by alias slug."""
        return self._entries

    @property
    def mapping_file(self) -> str:
        """Return resolved alias mapping path."""
        return str(self._resolve_mapping_path())

    async def async_refresh(self) -> dict[str, AliasMappingEntry]:
        """Reload mapping when file mtime changes."""
        path = self._resolve_mapping_path()

        try:
            stat = await self._hass.async_add_executor_job(path.stat)
        except FileNotFoundError:
            if self._entries:
                LOGGER.warning("Alias mapping file not found: %s. Clearing alias mapping.", path)
            self._last_mtime_ns = None
            self._last_path = path
            self._entries = {}
            return self._entries
        except OSError as err:
            LOGGER.warning("Unable to stat alias mapping file %s: %s", path, err)
            return self._entries

        mtime_ns = stat.st_mtime_ns
        if self._last_path == path and self._last_mtime_ns == mtime_ns:
            return self._entries

        try:
            raw_mapping = await self._hass.async_add_executor_job(self._load_yaml_mapping, path)
            parsed_mapping = self._parse_mapping(raw_mapping)
        except (OSError, TypeError, ValueError, yaml.YAMLError) as err:
            LOGGER.warning(
                "Failed to parse alias mapping file %s: %s. Keeping previous valid mapping.",
                path,
                err,
            )
            return self._entries

        self._entries = parsed_mapping
        self._last_path = path
        self._last_mtime_ns = mtime_ns
        LOGGER.debug("Loaded %s alias mappings from %s", len(parsed_mapping), path)
        return self._entries

    def _resolve_mapping_path(self) -> Path:
        """Resolve mapping path from config entry data/options."""
        configured = str(
            self._entry.options.get(
                CONF_ALIAS_MAPPING_FILE,
                self._entry.data.get(CONF_ALIAS_MAPPING_FILE, DEFAULT_ALIAS_MAPPING_FILE),
            )
        ).strip()

        if not configured:
            configured = DEFAULT_ALIAS_MAPPING_FILE

        path = Path(configured)
        if path.is_absolute():
            return path
        return Path(self._hass.config.path(configured))

    @staticmethod
    def _load_yaml_mapping(path: Path) -> dict:
        """Load alias YAML from disk."""
        with path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}

        if not isinstance(data, dict):
            raise TypeError("Alias mapping YAML top level must be an object (dict)")
        return data

    def _parse_mapping(self, raw_mapping: dict) -> dict[str, AliasMappingEntry]:
        """Validate and normalize alias mapping entries."""
        entries: dict[str, AliasMappingEntry] = {}
        for raw_alias, raw_mac in raw_mapping.items():
            if not isinstance(raw_alias, str):
                LOGGER.warning("Skipping alias mapping with non-string alias: %s", raw_alias)
                continue
            if not isinstance(raw_mac, str):
                LOGGER.warning("Skipping alias '%s' with non-string MAC", raw_alias)
                continue

            alias = raw_alias.strip()
            if not alias:
                LOGGER.warning("Skipping alias mapping with empty alias")
                continue

            alias_slug = slugify(alias, separator="_")
            if not alias_slug:
                LOGGER.warning("Skipping alias '%s' because slug is empty", alias)
                continue
            if alias_slug in entries:
                LOGGER.warning("Skipping alias '%s'. Slug collision on '%s'.", alias, alias_slug)
                continue

            mac = self._normalize_mac(raw_mac.strip())
            if mac is None:
                LOGGER.warning("Skipping alias '%s' because MAC '%s' is invalid", alias, raw_mac)
                continue

            entries[alias_slug] = AliasMappingEntry(alias=alias, slug=alias_slug, mac=mac)

        return entries
