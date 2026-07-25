# OpenWrt Ubus WiFi Presence

> Focused fork of
> [FUjr/homeassistant-openwrt-ubus](https://github.com/FUjr/homeassistant-openwrt-ubus)
> that keeps only WiFi presence tracking through OpenWrt ubus.

Home Assistant custom integration for tracking wireless clients across one or more
OpenWrt routers or access points.

## Features

- `device_tracker` entities with `home` / `not_home` state
- global `binary_sensor` entities indicating whether an SSID has any associated
  clients
- presence combined across multiple configured OpenWrt routers
- alias-to-MAC mappings managed through a file, the Home Assistant UI, or both
- stable alias tracker identities when a device MAC changes
- automatic ubus session renewal after a router restart
- reauthentication, reconfiguration, and runtime options flows

The integration intentionally does not collect wired clients, DHCP hostnames, client
IP addresses, system sensors, modem metrics, or router controls.

## Migration

### From the old `openwrt_ubus_wifi_presence` domain

1. Remove the old integration entry in **Settings -> Devices & Services**.
2. Install the current repository version and restart Home Assistant.
3. Add **OpenWrt Ubus WiFi Presence** again.
4. Update automations and dashboards that referenced old entity IDs.

### From earlier versions of this repository

1. Update the integration through HACS or copy the new files manually.
2. Restart Home Assistant.
3. Open **Configure** and verify:
   - `tracking_mode` (`known_or_alias` is recommended)
   - `mapping_source` (`hybrid` by default)
   - `alias_mapping_file` and/or `alias_mapping_ui`
4. Update aliases when device hardware changes.

The config entry migration removes obsolete per-client device-registry records once.
Existing scanner tracker entities and their entity registry settings are retained.

## Installation

### HACS custom repository

1. Open **HACS -> Integrations -> Custom repositories**.
2. Add this repository as category **Integration**.
3. Install **OpenWrt Ubus WiFi Presence**.
4. Restart Home Assistant.

### Manual

Copy `custom_components/openwrt_ubus` into the `custom_components` directory of your
Home Assistant configuration and restart Home Assistant.

## OpenWrt Requirements

Install and enable:

- `rpcd`
- `uhttpd-mod-ubus`
- `rpcd-mod-iwinfo`

Home Assistant must be able to reach the router's ubus HTTP endpoint. The configured
OpenWrt user needs permission for:

- `session.login` and `session.destroy`
- `iwinfo.devices`, `iwinfo.assoclist`, and `iwinfo.info`
- `network.wireless.status`
- `uci.get` for the compatibility fallback used by some OpenWrt versions

The exact methods exposed by a router can be checked over SSH with:

```sh
ubus -v list iwinfo
ubus -v list network.wireless
ubus -v list uci
```

## Configuration

In Home Assistant:

1. Go to **Settings -> Devices & Services -> Add Integration**.
2. Search for **OpenWrt Ubus WiFi Presence**.
3. Enter the host, credentials, and connection settings.

The configured `host` is the stable identity of the config entry. Use the optional
`ip_address` field when DNS and the address used for the connection should differ.

Runtime configuration paths:

- **Reauthenticate** updates username and password after authentication failure.
- **Reconfigure** updates connection parameters except `host`.
- **Options** updates tracking mode, alias mappings, and polling interval.

The default scan interval is 30 seconds.

## Tracking Modes

- `known_or_alias` (default): create trackers for aliases and MAC addresses known in
  the Home Assistant device registry.
- `all`: additionally create trackers for every currently observed WiFi client.

Entities excluded by the current filter are disabled and hidden by the integration,
not deleted. User-disabled entities remain disabled.

## Alias Mapping

Mapping sources:

- `file`: use only `alias_mapping_file`
- `ui`: use only YAML entered in `alias_mapping_ui`
- `hybrid`: combine both sources; the file wins when aliases produce the same slug

The default relative file path is `openwrt_ubus_aliases.yaml`, resolved inside the
Home Assistant configuration directory.

Example:

```yaml
my_phone: "AA:BB:CC:DD:EE:FF"
someones_phone: "11:22:33:44:55:66"
```

Changing the MAC under an existing alias keeps the same alias tracker entity and
starts following the new MAC. Aliases take precedence over plain MAC trackers, so a
mapped device is not exposed twice.

`!secret` is not supported inside alias mapping YAML. For GitOps-managed mappings,
prefer file mode and deploy the file through your normal configuration workflow.

## Device Trackers

Trackers use Home Assistant's scanner entity model. A tracker reports `home` when its
MAC is currently associated with any loaded OpenWrt config entry, and `not_home`
otherwise.

Each tracker can expose:

| Attribute | Meaning |
| --- | --- |
| `router` | Router or AP currently seeing the client |
| `ssid` | SSID reported for the wireless interface |
| `ap_device` | OpenWrt wireless interface, such as `phy0-ap0` |
| `mapped_mac` | MAC currently followed by the tracker |
| `mapping_exists` | Whether the current alias/MAC target still exists |
| `tracker_type` | `alias` or `mac` |
| `target_source` | `alias`, `known`, or `all` |
| `entity_key` | Stable internal tracker key |

The integration does not expose DHCP hostname or IP address attributes because its
presence source is `iwinfo.assoclist`, not a DHCP lease database.

## SSID Presence Sensors

The integration creates one global binary sensor for every discovered SSID.

- The sensor is `on` when at least one client is associated with that SSID on any
  configured router.
- `connected_clients` contains the number of unique associated MAC addresses.
- A client visible through multiple routers is counted once.
- The sensor is available only when every registered router coordinator has a
  successful latest update.

## Development

Use the repository scripts:

```bash
./script/setup/bootstrap
./script/check
./script/test
./script/hassfest
./script/develop
```

For implementation details, see
[`docs/development/ARCHITECTURE.md`](docs/development/ARCHITECTURE.md).

This repository retains development tooling derived from
[jpawlowski/hacs.integration_blueprint](https://github.com/jpawlowski/hacs.integration_blueprint),
but its runtime integration and project documentation are maintained independently.

## License

MIT. See [LICENSE](LICENSE).
