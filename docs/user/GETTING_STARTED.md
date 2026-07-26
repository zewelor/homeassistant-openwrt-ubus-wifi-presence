# Getting Started with OpenWrt Ubus WiFi Presence

This integration reads current WiFi associations from OpenWrt and creates:

- per-device `device_tracker` entities
- global `binary_sensor` entities per WiFi SSID

## Prerequisites

- Home Assistant with custom integration support
- OpenWrt with ubus RPC available through `uhttpd-mod-ubus`
- an OpenWrt user with the required ubus permissions
- network access from Home Assistant to the configured router host or IP address

The user needs access to:

- `session.login` and `session.destroy`
- `network.wireless.status`
- `uci.get`
- `iwinfo.devices`, `iwinfo.assoclist`, and `iwinfo.info`

## Installation

### HACS custom repository

1. Open HACS -> Integrations -> Custom repositories.
2. Add `https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence`.
3. Select category `Integration`.
4. Install `OpenWrt Ubus WiFi Presence`.
5. Restart Home Assistant.

### Manual installation

1. Download a release from this repository.
2. Copy `custom_components/openwrt_ubus` into the Home Assistant `custom_components/` directory.
3. Restart Home Assistant.

## Initial setup

1. Go to Settings -> Devices & Services.
2. Select Add Integration.
3. Search for `OpenWrt Ubus WiFi Presence`.
4. Enter connection credentials and tracking settings.

Setup fields include:

- connection: `host`, optional `ip_address`, HTTPS, port, endpoint, username, and password
- tracking: `tracking_mode`, `mapping_source`, `alias_mapping_file`, `alias_mapping_ui`, and scan interval

The configured `host` is the stable identity of the config entry and cannot be
changed through reconfigure.

## Runtime configuration

- **Reauthenticate** updates username and password after authentication fails.
- **Reconfigure** updates the connection address, protocol, port, endpoint, and credentials.
- **Options** updates tracking mode, alias mapping, mapping source, and scan interval.

## What gets created

### Device trackers

Each eligible alias or MAC target gets a `device_tracker` entity with
`home` / `not_home` state.

A tracker reports `home` when its MAC is associated with any loaded OpenWrt
router. Available attributes include:

- router host
- WiFi SSID
- OpenWrt AP interface
- mapped MAC
- target type and source

The integration does not retrieve DHCP hostname or client IP-address data.

### WiFi SSID presence sensors

The integration creates one global binary sensor per discovered WiFi SSID.

Each sensor:

- is on when at least one unique client is associated with the WiFi SSID
- aggregates all loaded OpenWrt config entries
- exposes `ssid` and `connected_clients` attributes

No wired-client trackers, router system sensors, switches, buttons, or services
are created.

## Alias mapping quick start

Choose a mapping source:

1. `file` for a GitOps-managed YAML file.
2. `ui` for YAML stored directly in integration options.
3. `hybrid` to combine both; file aliases override UI aliases with the same slug.

Example mapping:

```yaml
my_phone: "AA:BB:CC:DD:EE:FF"
someones_phone: "11:22:33:44:55:66"
```

Set `tracking_mode = known_or_alias` for a small, stable set of presence
entities. Use `tracking_mode = all` only when trackers for every observed client
are desired.

Changing the MAC value under an existing alias keeps the alias entity stable.

## Troubleshooting

- Connection errors: verify host/IP, credentials, ubus permissions, endpoint, port, and TLS settings.
- No trackers in `known_or_alias`: ensure devices have a network MAC connection in Home Assistant's Device Registry or add them to the alias mapping.
- Tracker mismatch after replacing hardware: update the MAC under the existing alias and reload the integration.
- Missing WiFi SSID sensor: verify that at least one successfully updated router reports the WiFi SSID.

Enable debug logging in `configuration.yaml` when needed:

```yaml
logger:
  logs:
    custom_components.openwrt_ubus: debug
```

## Next

- Detailed options: [CONFIGURATION.md](./CONFIGURATION.md)
- Runtime architecture: [ARCHITECTURE.md](../development/ARCHITECTURE.md)
- Main documentation and migration notes: [README](../../README.md)
- Issues: <https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/issues>
