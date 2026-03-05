# OpenWrt Ubus WiFi Presence

> Fork notice: This project is a focused fork of
> [FUjr/homeassistant-openwrt-ubus](https://github.com/FUjr/homeassistant-openwrt-ubus)
> and keeps only WiFi presence tracking (`home` / `not_home`) via ubus.

Home Assistant custom integration for tracking wireless clients connected to OpenWrt.

> Migration note: starting with `v0.2.0`, integration domain is `openwrt_ubus`.
> Existing instances using the previous fork domain must remove and add the integration again.

## Migration Existing Installations

### From old fork/domain (`openwrt_ubus_wifi_presence`)

1. In Home Assistant go to **Settings -> Devices & Services** and remove old integration entry.
2. Install this repository version and restart Home Assistant.
3. Add integration again as **OpenWrt Ubus WiFi Presence**.
4. Reassign entities in automations/scripts to new entity IDs (domain is now `openwrt_ubus`).

### From earlier versions of this repository

1. Update integration in HACS (or copy updated `custom_components/openwrt_ubus` manually).
2. Restart Home Assistant.
3. Open integration **Configure** and verify:
   - `tracking_mode` (`known_or_alias` recommended)
   - `alias_mapping_file` (default `/config/openwrt_ubus_aliases.yaml`)
4. If you use aliases, create/update mapping file and reload integration.
5. Check automations that referenced old per-MAC trackers and switch to alias trackers where needed.

## Scope

- Device tracker only (`device_tracker`)
- Wireless clients only (no wired tracking)
- Presence state only (`home` / `not_home`)
- Optional metadata attributes: hostname, IP, SSID, AP interface

Not included:

- System sensors
- QModem/mwan3 sensors
- Switches/buttons/services

## Installation

### HACS (Custom Repository)

1. Open HACS -> Integrations -> Custom repositories.
2. Add this repository URL as category `Integration`.
3. Install `OpenWrt Ubus WiFi Presence`.
4. Restart Home Assistant.

### Manual

1. Copy `custom_components/openwrt_ubus` to your HA config directory under `custom_components/`.
2. Restart Home Assistant.

## OpenWrt prerequisites

- `rpcd`
- `uhttpd-mod-ubus`
- A user with ubus permissions for:
  - `session.login`, `session.list`, `session.destroy`
  - `iwinfo.devices`, `iwinfo.assoclist` and/or `hostapd.*.get_clients`
  - `network.wireless.status`
  - `uci.get` and `file.read` (for DHCP name/IP mapping)

## Configuration

In Home Assistant:

1. Settings -> Devices & Services -> Add Integration.
2. Search for `OpenWrt Ubus WiFi Presence`.
3. Fill host/user/password and backend options.

Runtime management paths:

- Reauthenticate: updates credentials when auth fails
- Reconfigure: updates connection parameters except `host`
- Options: updates tracking/polling behavior

Note: `host` is treated as stable after initial setup.

Recommended values:

- Wireless backend: `iwinfo` (or `hostapd` if preferred)
- DHCP source: `dnsmasq`
- Scan interval: `30` seconds

Tracking options:

- Tracking mode:
  - `known_or_alias` (default): track only devices known in HA (device registry MACs) and aliases from file
  - `all`: track all observed WiFi clients
- Alias mapping file: default `openwrt_ubus_aliases.yaml` (resolved inside `/config`)

Alias mapping example:

```yaml
moj_phone: "AA:BB:CC:DD:EE:FF"
someones_phone: "11:22:33:44:55:66"
```

Behavior notes:

- Alias entities are created automatically, no manual enabling of per-MAC entities required
- Changing MAC under the same alias keeps the same alias tracker entity and starts tracking the new MAC
- Aliases have priority over plain MAC trackers (no duplicates for the same MAC)
- In `known_or_alias`, "known" means devices present in HA device registry with a MAC connection
- Entities filtered out by current mode are disabled/hidden by integration (not deleted)

## Entity Model

- Trackers are implemented as `ScannerEntity` (`device_tracker`) and focus only on `home` / `not_home`
- Home Assistant may not show a long per-client device list under the hub card; this is expected for scanner-based trackers
- The same physical device (MAC) can still be linked across multiple integrations in HA

## Alias Mapping Workflow

1. Create `/config/openwrt_ubus_aliases.yaml`.
2. Add entries in format `alias: "AA:BB:CC:DD:EE:FF"`.
3. Keep integration option `tracking_mode = known_or_alias` for clean presence-only setup.
4. Update MAC under existing alias when hardware changes; the alias entity stays stable.

## Development

Use project scripts only:

- `./script/setup/bootstrap`
- `./script/develop`
- `./script/check`
- `./script/hassfest`

### Development Boilerplate

This repository uses development scaffolding and workflow scripts based on:

- [jpawlowski/hacs.integration_blueprint](https://github.com/jpawlowski/hacs.integration_blueprint)

The blueprint provided the local HA development scripts, CI workflow layout, and project tooling baseline.

## License

MIT (see [LICENSE](LICENSE)).
