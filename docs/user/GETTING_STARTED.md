# Getting Started with OpenWrt Ubus WiFi Presence

This integration tracks associated WiFi clients from OpenWrt and creates:

- `device_tracker` entities with `home` / `not_home` state;
- global SSID presence `binary_sensor` entities.

## Prerequisites

- Home Assistant with custom integrations support
- OpenWrt with `rpcd`, `uhttpd-mod-ubus`, and `rpcd-mod-iwinfo`
- an OpenWrt user with access to the required ubus methods
- network access from Home Assistant to the router host or IP address

Required ubus access:

- `session.login` and `session.destroy`
- `iwinfo.devices`, `iwinfo.assoclist`, and `iwinfo.info`
- `network.wireless.status`
- `uci.get` for the wireless-status compatibility fallback

## Installation

### Via HACS

1. Open **HACS -> Integrations -> Custom repositories**.
2. Add `https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence`.
3. Select category **Integration**.
4. Install **OpenWrt Ubus WiFi Presence**.
5. Restart Home Assistant.

### Manual installation

1. Download a release from this repository.
2. Copy `custom_components/openwrt_ubus` into the `custom_components` directory of
   your Home Assistant configuration.
3. Restart Home Assistant.

## Initial Setup

1. Go to **Settings -> Devices & Services**.
2. Select **Add Integration**.
3. Search for **OpenWrt Ubus WiFi Presence**.
4. Enter the connection credentials and tracking settings.

Connection fields:

- stable router `host`
- optional connection `ip_address`
- HTTP or HTTPS, port, endpoint, and TLS verification
- username and password

Tracking fields:

- `tracking_mode`
- `mapping_source`
- `alias_mapping_file`
- `alias_mapping_ui`
- `scan_interval`

## Runtime Configuration

- **Reauthenticate** updates username and password when authentication fails.
- **Reconfigure** updates connection settings except the stable `host` identity.
- **Options** updates tracking mode, alias mappings, and scan interval.

## What Gets Created

### Device trackers

Trackers report `home` when their MAC is associated with any configured OpenWrt
router, and `not_home` otherwise.

Available metadata can include:

- router host
- SSID
- OpenWrt AP interface
- mapped MAC
- tracker type and mapping source

The integration does not provide DHCP hostname or client IP attributes.

### SSID presence sensors

One global binary sensor is created for every discovered SSID.

- `on`: at least one client is associated with the SSID
- `off`: no clients are associated with the SSID
- `connected_clients`: number of unique associated MAC addresses across all routers

## Alias Mapping Quick Start

Choose a mapping source:

1. `file` for a GitOps-managed YAML file.
2. `ui` for YAML stored only in integration options.
3. `hybrid` to combine both; the file wins on alias slug collisions.

Example mapping:

```yaml
my_phone: "AA:BB:CC:DD:EE:FF"
someones_phone: "11:22:33:44:55:66"
```

Use `tracking_mode = known_or_alias` for a small, stable set of presence entities.
When hardware changes, update the MAC under the existing alias to keep the same
tracker identity.

## Troubleshooting

- Connection errors: verify the host/IP, endpoint, credentials, ubus ACLs, and TLS
  settings.
- No trackers in `known_or_alias`: make sure devices have a network MAC connection in
  the Home Assistant device registry or are present in the alias mapping.
- No SSID sensors: verify `network.wireless.status` and `iwinfo.info` permissions and
  confirm the router reports an SSID for its AP interfaces.
- Device remains `not_home`: run `ubus call iwinfo assoclist '{"device":"<interface>"}'`
  over SSH and verify that the MAC appears with `authorized: true`.

Enable debug logging when needed:

```yaml
logger:
  logs:
    custom_components.openwrt_ubus: debug
```

## Next

- [Detailed configuration](./CONFIGURATION.md)
- [Architecture](../development/ARCHITECTURE.md)
- [Main README](../../README.md)
- [Issue tracker](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/issues)
