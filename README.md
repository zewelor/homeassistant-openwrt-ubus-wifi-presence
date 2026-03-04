# OpenWrt Ubus WiFi Presence

> Fork notice: This project is a focused fork of
> [FUjr/homeassistant-openwrt-ubus](https://github.com/FUjr/homeassistant-openwrt-ubus)
> and keeps only WiFi presence tracking (`home` / `not_home`) via ubus.

Home Assistant custom integration for tracking wireless clients connected to OpenWrt.

> Migration note: starting with `v0.2.0`, integration domain is `openwrt_ubus`.
> Existing instances using the previous fork domain must remove and add the integration again.
> If HACS fails to download `v0.2.0` with "No content to download", update to `v0.2.1+`.

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

Recommended values:

- Wireless backend: `iwinfo` (or `hostapd` if preferred)
- DHCP source: `dnsmasq`
- Scan interval: `30` seconds

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
