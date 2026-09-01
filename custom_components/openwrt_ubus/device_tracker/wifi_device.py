"""Device tracker entity for OpenWrt Ubus WiFi Presence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.openwrt_ubus.data import TrackerTarget
from custom_components.openwrt_ubus.entity import OpenWrtUbusWifiPresenceEntity
from homeassistant.components.device_tracker.const import SourceType
from homeassistant.components.device_tracker.entity import ScannerEntity
from homeassistant.util import slugify

if TYPE_CHECKING:
    from custom_components.openwrt_ubus.coordinator import OpenWrtUbusWifiPresenceCoordinator
    from custom_components.openwrt_ubus.device_tracker.manager import OpenWrtUbusWifiPresenceDeviceTrackerManager


class OpenWrtUbusWifiPresenceDeviceTracker(ScannerEntity, OpenWrtUbusWifiPresenceEntity):
    """Represent one global WiFi client tracker target."""

    _attr_source_type = SourceType.ROUTER

    def __init__(
        self,
        *,
        manager: OpenWrtUbusWifiPresenceDeviceTrackerManager,
        coordinator: OpenWrtUbusWifiPresenceCoordinator,
        owner_entry_id: str,
        target: TrackerTarget,
    ) -> None:
        """Initialize a tracker owned by one platform but backed by all routers."""
        super().__init__(coordinator)
        self._manager = manager
        self._owner_entry_id = owner_entry_id
        self._entity_key = target.entity_key
        self._fallback_target = target
        self._attr_suggested_object_id = self._build_suggested_object_id(target.entity_key)

    async def async_added_to_hass(self) -> None:
        """Register the tracker after Home Assistant accepts it."""
        await super().async_added_to_hass()
        self._manager.async_entity_added(self)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister the tracker when Home Assistant removes it."""
        self._manager.async_entity_removed(self)
        await super().async_will_remove_from_hass()

    @property
    def entity_key(self) -> str:
        """Return the stable global tracker key."""
        return self._entity_key

    @property
    def owner_entry_id(self) -> str:
        """Return the config entry whose platform currently owns this entity."""
        return self._owner_entry_id

    @property
    def unique_id(self) -> str:
        """Return a router-independent registry identity."""
        return self._entity_key

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Enable trackers even when no matching Device Registry entry exists."""
        return True

    @property
    def _target(self) -> TrackerTarget:
        return self._manager.target_for_key(self._entity_key) or self._fallback_target

    @staticmethod
    def _build_suggested_object_id(entity_key: str) -> str:
        """Build a stable, readable suggested object ID."""
        if entity_key.startswith("alias_"):
            return entity_key.removeprefix("alias_")
        if entity_key.startswith("mac_"):
            mac = entity_key.removeprefix("mac_").replace(":", "").lower()
            return f"mac_{mac}"
        return slugify(entity_key, separator="_")

    @property
    def name(self) -> str:
        """Return the latest global target display name."""
        return self._target.display_name

    @property
    def available(self) -> bool:
        """Return whether global router data supports a certain state."""
        return self._manager.tracker_available(self._entity_key)

    @property
    def is_connected(self) -> bool:
        """Return whether any healthy router currently sees this target."""
        return self._manager.current_observation_for_key(self._entity_key) is not None

    @property
    def mac_address(self) -> str | None:
        """Return the current unambiguous target MAC."""
        return self._manager.resolved_mac_for_key(self._entity_key)

    @property
    def extra_state_attributes(self) -> dict[str, str | bool | None]:
        """Return stable target metadata and current association context."""
        observation = self._manager.current_observation_for_key(self._entity_key)
        target = self._target
        return {
            "router": self._manager.last_or_current_router_for_key(self._entity_key),
            "entity_key": self._entity_key,
            "tracker_type": target.tracker_type.value,
            "target_source": target.source.value,
            "mapped_mac": self._manager.resolved_mac_for_key(self._entity_key),
            "mapping_exists": self._manager.target_is_current(self._entity_key),
            "ssid": observation.device.ssid if observation else None,
            "ap_device": observation.device.ap_device if observation else None,
        }
