# Getting Started with OpenWrt Ubus WiFi Presence

This integration tracks WiFi client presence from OpenWrt (`home` / `not_home`) as `device_tracker` entities.

## Prerequisites

- Home Assistant with custom integrations support
- OpenWrt with ubus RPC available (`uhttpd-mod-ubus`)
- OpenWrt user with required ubus permissions
- Network access from Home Assistant to router host/IP

## Installation

### Via HACS (recommended)

1. Open HACS -> Integrations -> Custom repositories.
2. Add repository URL: `https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence`.
3. Category: `Integration`.
4. Install `OpenWrt Ubus WiFi Presence`.
5. Restart Home Assistant.

### Manual installation

1. Download release from this repository.
2. Copy `custom_components/openwrt_ubus` to your HA config directory under `custom_components/`.
3. Restart Home Assistant.

## Initial setup (Config Flow)

1. Go to Settings -> Devices & Services.
2. Click Add Integration.
3. Search for `OpenWrt Ubus WiFi Presence`.
4. Fill connection credentials and tracking settings.

Setup fields include:

- Connection: `host`, optional `ip_address`, TLS/port/endpoint, username/password
- Tracking: `tracking_mode`, `alias_mapping_file`, backend selections, scan interval

## Runtime configuration paths

- Reauthenticate: when credentials fail, integration opens reauth flow for username/password.
- Reconfigure: update connection settings except `host` (host remains stable after setup).
- Options: update tracking behavior (`tracking_mode`, alias file, backends, scan interval).

## What gets created

- Platform: `device_tracker`
- States: `home` / `not_home`
- Optional attributes: hostname, IP, SSID, AP interface

No sensors, switches, buttons, or services are created by this integration.

## Alias mapping quick start

Create `/config/openwrt_ubus_aliases.yaml`:

```yaml
moj_phone: "AA:BB:CC:DD:EE:FF"
someones_phone: "11:22:33:44:55:66"
```

Then set `tracking_mode = known_or_alias` for clean, stable presence entities.

## Troubleshooting

- Connection errors: verify host/IP, credentials, ubus permissions, and TLS settings.
- No trackers in `known_or_alias`: ensure devices are known in HA device registry or defined in alias file.
- Tracker mismatch after device replacement: update alias MAC mapping and reload integration.

Enable debug logs in `configuration.yaml` if needed:

```yaml
logger:
  logs:
    custom_components.openwrt_ubus: debug
```

## Next

- Detailed options: [CONFIGURATION.md](./CONFIGURATION.md)
- Main docs and migration notes: [README](../../README.md)
- Issues: <https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/issues>
