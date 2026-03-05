"""Alias mapping loader for OpenWrt WiFi presence tracking."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from custom_components.openwrt_ubus.const import (
    CONF_ALIAS_MAPPING_FILE,
    CONF_ALIAS_MAPPING_UI,
    CONF_MAPPING_SOURCE,
    DEFAULT_ALIAS_MAPPING_FILE,
    DEFAULT_ALIAS_MAPPING_UI,
    DEFAULT_MAPPING_SOURCE,
    LOGGER,
    MAPPING_SOURCES,
)
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
    """Load and cache alias->MAC mapping from file/UI based on source mode."""

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
        self._last_ui_mapping_raw: str | None = None
        self._file_entries: dict[str, AliasMappingEntry] = {}
        self._ui_entries: dict[str, AliasMappingEntry] = {}
        self._entries: dict[str, AliasMappingEntry] = {}
        self._mapping_summary: dict[str, int] = {"file": 0, "ui": 0, "effective": 0}

    @property
    def mapping(self) -> dict[str, AliasMappingEntry]:
        """Return current mapping keyed by alias slug."""
        return self._entries

    @property
    def mapping_file(self) -> str:
        """Return resolved alias mapping path."""
        return str(self._resolve_mapping_path())

    @property
    def mapping_source(self) -> str:
        """Return active alias source mode."""
        raw_mode = self._entry.options.get(CONF_MAPPING_SOURCE, self._entry.data.get(CONF_MAPPING_SOURCE, ""))
        mode = str(raw_mode).strip().lower()
        return mode if mode in MAPPING_SOURCES else DEFAULT_MAPPING_SOURCE

    @property
    def mapping_summary(self) -> dict[str, int]:
        """Return summary of loaded alias mappings by source."""
        return dict(self._mapping_summary)

    async def async_refresh(self) -> dict[str, AliasMappingEntry]:
        """Refresh alias mappings from selected source mode."""
        mode = self.mapping_source

        if mode in ("file", "hybrid"):
            await self._async_refresh_file_entries()
        if mode in ("ui", "hybrid"):
            self._refresh_ui_entries()

        if mode == "file":
            self._entries = dict(self._file_entries)
        elif mode == "ui":
            self._entries = dict(self._ui_entries)
        else:
            merged = dict(self._ui_entries)
            for alias_slug, file_entry in self._file_entries.items():
                ui_entry = merged.get(alias_slug)
                if ui_entry is not None and ui_entry.mac != file_entry.mac:
                    LOGGER.debug(
                        "Alias '%s' from file overrides UI MAC %s -> %s",
                        alias_slug,
                        ui_entry.mac,
                        file_entry.mac,
                    )
                merged[alias_slug] = file_entry
            self._entries = merged

        self._mapping_summary = {
            "file": len(self._file_entries),
            "ui": len(self._ui_entries),
            "effective": len(self._entries),
        }
        return self._entries

    def _resolve_mapping_path(self) -> Path:
        """Resolve mapping path from config entry data/options."""
        configured_value = self._entry.options.get(
            CONF_ALIAS_MAPPING_FILE,
            self._entry.data.get(CONF_ALIAS_MAPPING_FILE, DEFAULT_ALIAS_MAPPING_FILE),
        )
        configured = configured_value.strip() if isinstance(configured_value, str) else ""

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

    def _resolve_ui_mapping(self) -> str:
        """Resolve UI YAML alias mapping from config/options."""
        configured_value = self._entry.options.get(
            CONF_ALIAS_MAPPING_UI,
            self._entry.data.get(CONF_ALIAS_MAPPING_UI, DEFAULT_ALIAS_MAPPING_UI),
        )
        if not isinstance(configured_value, str):
            return ""
        return configured_value.strip()

    @staticmethod
    def _load_ui_yaml_mapping(raw_mapping: str) -> dict:
        """Load alias YAML from UI text option."""
        data = yaml.safe_load(raw_mapping) or {}
        if not isinstance(data, dict):
            raise TypeError("UI alias mapping must be a YAML object (dict)")
        return data

    async def _async_refresh_file_entries(self) -> None:
        """Reload file-based alias mapping when mtime changes."""
        path = self._resolve_mapping_path()

        try:
            stat = await self._hass.async_add_executor_job(path.stat)
        except FileNotFoundError:
            if self._file_entries:
                LOGGER.warning("Alias mapping file not found: %s. Clearing file alias mapping.", path)
            self._last_mtime_ns = None
            self._last_path = path
            self._file_entries = {}
            return
        except OSError as err:
            LOGGER.warning("Unable to stat alias mapping file %s: %s", path, err)
            return

        mtime_ns = stat.st_mtime_ns
        if self._last_path == path and self._last_mtime_ns == mtime_ns:
            return

        try:
            raw_mapping = await self._hass.async_add_executor_job(self._load_yaml_mapping, path)
            parsed_mapping = self._parse_mapping(raw_mapping)
        except (OSError, TypeError, ValueError, yaml.YAMLError) as err:
            LOGGER.warning(
                "Failed to parse alias mapping file %s: %s. Keeping previous valid file mapping.",
                path,
                err,
            )
            return

        self._file_entries = parsed_mapping
        self._last_path = path
        self._last_mtime_ns = mtime_ns
        LOGGER.debug("Loaded %s alias mappings from %s", len(parsed_mapping), path)

    def _refresh_ui_entries(self) -> None:
        """Reload UI-based alias mapping when option value changes."""
        raw_mapping = self._resolve_ui_mapping()
        if self._last_ui_mapping_raw == raw_mapping:
            return

        if not raw_mapping:
            self._ui_entries = {}
            self._last_ui_mapping_raw = raw_mapping
            return

        try:
            data = self._load_ui_yaml_mapping(raw_mapping)
            parsed_mapping = self._parse_mapping(data)
        except (TypeError, ValueError, yaml.YAMLError) as err:
            LOGGER.warning(
                "Failed to parse UI alias mapping. Keeping previous valid UI mapping: %s",
                err,
            )
            self._last_ui_mapping_raw = raw_mapping
            return

        self._ui_entries = parsed_mapping
        self._last_ui_mapping_raw = raw_mapping
        LOGGER.debug("Loaded %s alias mappings from UI options", len(parsed_mapping))

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
