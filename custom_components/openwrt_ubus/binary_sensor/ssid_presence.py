"""WiFi SSID presence binary sensor."""

from hashlib import sha1
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.util import slugify

if TYPE_CHECKING:
    from custom_components.openwrt_ubus.binary_sensor import OpenWrtUbusSsidPresenceManager

SSID_UNIQUE_ID_PREFIX = "openwrt_wifi_ssid_presence_"


def ssid_unique_id(ssid: str) -> str:
    """Return the stable unique ID for one WiFi SSID sensor."""
    ssid_hash = sha1(ssid.encode(), usedforsecurity=False).hexdigest()[:12]
    return f"{SSID_UNIQUE_ID_PREFIX}{ssid_hash}"


class OpenWrtUbusSsidPresenceBinarySensor(BinarySensorEntity):
    """Binary sensor that is on when any client is connected to one WiFi SSID."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "wifi_ssid_presence"

    def __init__(self, manager: OpenWrtUbusSsidPresenceManager, ssid: str) -> None:
        """Initialize the WiFi SSID presence sensor."""
        self._manager = manager
        self._ssid = ssid
        slug = slugify(ssid, separator="_")
        self._attr_translation_placeholders = {"ssid": ssid}
        self._attr_unique_id = ssid_unique_id(ssid)
        self._attr_suggested_object_id = f"openwrt_wifi_{slug}_presence"

    async def async_added_to_hass(self) -> None:
        """Register the entity after Home Assistant accepted it."""
        await super().async_added_to_hass()
        self._manager.async_entity_added(self)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister the entity when Home Assistant removes it."""
        self._manager.async_entity_removed(self)
        await super().async_will_remove_from_hass()

    @property
    def ssid(self) -> str:
        """Return the WiFi SSID represented by this sensor."""
        return self._ssid

    @property
    def is_on(self) -> bool:
        """Return true when at least one client is connected to this WiFi SSID."""
        return self._manager.connected_count_for_ssid(self._ssid) > 0

    @property
    def available(self) -> bool:
        """Return true when all enabled routers have fresh coordinator data."""
        return self._manager.all_updates_successful

    @property
    def extra_state_attributes(self) -> dict[str, str | int]:
        """Return attributes for diagnostics and automations."""
        return {
            "ssid": self._ssid,
            "connected_clients": self._manager.connected_count_for_ssid(self._ssid),
        }
