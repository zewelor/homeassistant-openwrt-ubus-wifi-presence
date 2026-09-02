# OpenWrt Ubus WiFi Presence

> Fork notice: This project is a focused fork of
> [FUjr/homeassistant-openwrt-ubus](https://github.com/FUjr/homeassistant-openwrt-ubus)
> and keeps only WiFi presence tracking via ubus.

Home Assistant custom integration for tracking wireless clients connected to
OpenWrt. It provides global per-device trackers and aggregated WiFi SSID presence sensors.

## Migrating existing installations

### From the old fork/domain (`openwrt_ubus_wifi_presence`)

1. In Home Assistant go to **Settings -> Devices & Services** and remove the old integration entry.
2. Install this repository version and restart Home Assistant.
3. Add the integration again as **OpenWrt Ubus WiFi Presence**.
4. Reassign entities in automations and scripts to the new entity IDs. The domain is now `openwrt_ubus`.

### From earlier versions of this repository

1. Update the integration in HACS, or copy the updated `custom_components/openwrt_ubus` directory manually.
2. Restart Home Assistant.
3. Open integration **Configure** and verify:
   - `tracking_mode` (`known_or_alias` recommended)
   - `alias_mapping_file` (default `/config/openwrt_ubus_aliases.yaml`)
   - `mapping_source` (`hybrid` by default)
4. Update aliases in the selected mapping source and reload the integration when needed.
5. Check automations that referenced old per-MAC trackers and switch to alias trackers where appropriate.

The version-2 config-entry migration automatically removes legacy per-client
Device Registry entries left by versions from before scanner-based trackers.

Global tracker identities are not migrated from older per-router or MAC-based
unique IDs. Remove obsolete tracker entries from Home Assistant's Entity
Registry if they are still present after upgrading.

## Scope

Included:

- one global `device_tracker` entity per eligible alias or MAC target
- global `binary_sensor` entities showing whether a WiFi SSID has connected clients
- wireless clients reported by `iwinfo`
- multiple OpenWrt routers and access points
- router, WiFi SSID, and AP-interface metadata

Not included:

- wired client tracking
- DHCP hostname or client IP enrichment
- router system, QModem, or mwan3 sensors
- switches, buttons, or services

## Installation

### HACS custom repository

1. Open HACS -> Integrations -> Custom repositories.
2. Add this repository URL as category `Integration`.
3. Install `OpenWrt Ubus WiFi Presence`.
4. Restart Home Assistant.

### Manual

1. Copy `custom_components/openwrt_ubus` to the Home Assistant config directory under `custom_components/`.
2. Restart Home Assistant.

## OpenWrt prerequisites

Install and enable:

- `rpcd`
- `uhttpd-mod-ubus`

The configured OpenWrt user needs ubus permissions for:

- `session.login` and `session.destroy`
- `network.wireless.status`
- `uci.get`
- `iwinfo.devices`, `iwinfo.assoclist`, and `iwinfo.info`

`uci.get` is used only as a compatibility fallback on systems where
`network.wireless.status` must be queried per radio device.

## Configuration

In Home Assistant:

1. Go to Settings -> Devices & Services -> Add Integration.
2. Search for `OpenWrt Ubus WiFi Presence`.
3. Fill in the connection credentials and tracking settings.

Runtime management paths:

- **Reauthenticate** updates credentials after an authentication failure.
- **Reconfigure** updates connection parameters except `host`.
- **Options** updates tracking, mapping, and polling behavior.

`host` is treated as the stable config-entry identity after initial setup.

Recommended scan interval: `30` seconds.

### Tracking mode

- `known_or_alias` (default): track aliases and devices known in Home Assistant's Device Registry by MAC address.
- `all`: also create trackers for every currently observed WiFi client.

### Alias mapping source

- `file`: use only `alias_mapping_file`.
- `ui`: use only multiline YAML stored in integration options.
- `hybrid` (default): combine both sources; the file wins on alias-slug collisions.

The default file is `openwrt_ubus_aliases.yaml`, resolved inside the Home
Assistant config directory.

Example for either mapping source:

```yaml
my_phone: "AA:BB:CC:DD:EE:FF"
someones_phone: "11:22:33:44:55:66"
```

Behavior notes:

- Alias entities are created automatically.
- Changing the MAC under an existing alias keeps the same alias tracker entity.
- Aliases take priority over plain MAC trackers for the same MAC.
- The same alias mapped to different MACs on different routers remains unavailable until the conflict is fixed.
- Entities filtered out by the current tracking mode are hidden and disabled by the integration, not deleted.

## Device trackers

Trackers are implemented as Home Assistant `ScannerEntity` entities.

Each target has one global tracker, even when it can roam between multiple
configured OpenWrt routers. A tracker reports `home` when any successfully
updated router sees its MAC. It reports `not_home` only when every enabled
router has updated successfully and none sees the MAC. Otherwise it is
`unavailable`, so stale or incomplete data cannot publish a false absence.

When multiple routers report the same MAC, the integration prefers the most
recent station activity, then the strongest signal, and finally a deterministic
router/AP ordering.

Each tracker exposes:

| Attribute        | Description                                   | Example                    |
| ---------------- | --------------------------------------------- | -------------------------- |
| `router`         | Current or last runtime router for the client | `router-office.lan`        |
| `ssid`           | WiFi SSID name, when available                | `MyNetwork_5G`             |
| `ap_device`      | OpenWrt wireless interface                    | `phy0-ap0`                 |
| `mapped_mac`     | MAC followed by the tracker                   | `11:22:33:44:55:66`        |
| `mapping_exists` | Whether the current target definition exists  | `true`                     |
| `tracker_type`   | `alias` or `mac`                              | `alias`                    |
| `target_source`  | `alias`, `known`, or `all`                    | `alias`                    |
| `entity_key`     | Internal stable target key                    | `alias_living_room_sensor` |

The integration's runtime station data comes directly from
`iwinfo.assoclist`. It does not provide DHCP hostname or IP-address properties.
The last router is kept only in memory and resets when Home Assistant restarts.
Home Assistant hides custom attributes while an entity is `unavailable`; the
remembered router is shown again when the tracker becomes available.

### Alias example

Create `/config/openwrt_ubus_aliases.yaml`:

```yaml
living_room_sensor: "11:22:33:44:55:66"
bedroom_lamp: "AA:BB:CC:DD:EE:FF"
```

The `device_tracker.living_room_sensor` entity can then expose:

```yaml
router: router-office.lan
ssid: HomeNetwork_5G
ap_device: phy0-ap0
mapped_mac: 11:22:33:44:55:66
mapping_exists: true
tracker_type: alias
target_source: alias
entity_key: alias_living_room_sensor
```

## WiFi SSID presence sensors

The integration creates one global binary sensor per discovered WiFi SSID, for
example:

```text
binary_sensor.openwrt_wifi_homenetwork_presence
```

The sensor:

- is on when at least one client is associated with that WiFi SSID
- aggregates all loaded OpenWrt config entries
- deduplicates a MAC reported by more than one router
- exposes `ssid` and `connected_clients` attributes

A reported WiFi SSID can keep an off sensor while it has zero associated
clients. Cleanup runs only after every enabled router has a registered
coordinator, a successful latest update, and a complete WiFi SSID inventory.
A WiFi SSID absent from that authoritative union is removed; permanently
renaming it removes the old sensor and creates one for the new name. Failed
updates, partial compatibility fallbacks, and normal config-entry reloads do not
trigger removal.

## Alias mapping security

- `!secret` is not supported inside alias mappings.
- UI mapping stores plain MAC values in config-entry options.
- For GitOps or stricter secret management, prefer `mapping_source = file` and manage the file through the deployment system.

## Development

Use the project scripts:

- `./script/setup/bootstrap`
- `./script/develop`
- `./script/check`
- `./script/hassfest`

See [the architecture document](docs/development/ARCHITECTURE.md) for the current
runtime design.

### Troubleshooting development environments

After a system Python upgrade, `.local/ha-venv` or `.venv` can point to the old
Python installation. Symptoms include missing `pre_commit`, `ruff`, `codespell`,
or `pyright` modules.

Rebuild the environment:

```bash
rm -rf .local/ha-venv .venv
./script/setup/bootstrap
```

### Development tooling origin

The repository's development scripts and workflow layout originated from
[jpawlowski/hacs.integration_blueprint](https://github.com/jpawlowski/hacs.integration_blueprint).
The runtime integration is maintained specifically for OpenWrt WiFi presence.

## License

MIT (see [LICENSE](LICENSE)).
