# OpenWrt Ubus WiFi Presence

> Fork notice: This project is a focused fork of
> [FUjr/homeassistant-openwrt-ubus](https://github.com/FUjr/homeassistant-openwrt-ubus)
> and keeps only WiFi presence tracking (`home` / `not_home`) via ubus.

Home Assistant custom integration for tracking wireless clients connected to OpenWrt.

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
   - `mapping_source` (`hybrid` by default)
4. If you use aliases, update alias mapping in selected source (`alias_mapping_file` and/or `alias_mapping_ui`) and reload integration.
5. Check automations that referenced old per-MAC trackers and switch to alias trackers where needed.

## Scope

- Device tracker only (`device_tracker`)
- Wireless clients only (no wired tracking)
- Presence state only (`home` / `not_home`)
- Optional metadata attributes: SSID, AP interface

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

## OpenWrt Prerequisites

- `rpcd`
- `uhttpd-mod-ubus`
- A user with ubus permissions for:
  - `session.login`, `session.list`, `session.destroy`
  - `iwinfo.devices`, `iwinfo.assoclist`, `iwinfo.info`
  - `network.wireless.status`

## Configuration

In Home Assistant:

1. Settings -> Devices & Services -> Add Integration.
2. Search for `OpenWrt Ubus WiFi Presence`.
3. Fill host/user/password and connection settings.

Runtime management paths:

- Reauthenticate: updates credentials when auth fails
- Reconfigure: updates connection parameters except `host`
- Options: updates tracking/polling behavior

Note: `host` is treated as stable after initial setup.

Recommended values:

- Scan interval: `30` seconds

Tracking options:

- Tracking mode:
  - `known_or_alias` (default): track only devices known in HA (device registry MACs) and aliases from file
  - `all`: track all observed WiFi clients
- Alias mapping source:
  - `file`: use only `alias_mapping_file`
  - `ui`: use only `alias_mapping_ui` YAML from integration options
  - `hybrid` (default): combine UI + file; file wins on alias collision
- Alias mapping file: default `openwrt_ubus_aliases.yaml` (resolved inside `/config`)
- Alias mapping UI: multiline YAML (`alias: "AA:BB:CC:DD:EE:FF"`)

Alias mapping example:

```yaml
my_phone: "AA:BB:CC:DD:EE:FF"
someones_phone: "11:22:33:44:55:66"
```

Behavior notes:

- Alias entities are created automatically, no manual enabling of per-MAC entities required
- Changing MAC under the same alias keeps the same alias tracker entity and starts tracking the new MAC
- Aliases have priority over plain MAC trackers (no duplicates for the same MAC)
- In `hybrid` source mode, file aliases override UI aliases with the same slug
- In `known_or_alias`, "known" means devices present in HA device registry with a MAC connection
- Entities filtered out by current mode are disabled/hidden by integration (not deleted)

## Entity Model

- Trackers are implemented as `ScannerEntity` (`device_tracker`) and focus only on `home` / `not_home`
- Home Assistant may not show a long per-client device list under the hub card; this is expected for scanner-based trackers
- The same physical device (MAC) can still be linked across multiple integrations in HA

## Alias Mapping Workflow

1. Choose `mapping_source` in integration options (`file`, `ui`, or `hybrid`).
2. If using file mode/hybrid, create `/config/openwrt_ubus_aliases.yaml` with `alias: "AA:BB:CC:DD:EE:FF"`.
3. If using UI mode/hybrid, fill `alias_mapping_ui` with the same YAML format.
4. Keep `tracking_mode = known_or_alias` for clean presence-only setup.
5. Update MAC under existing alias when hardware changes; alias entity stays stable.

## Entity Attributes

Each device tracker entity exposes the following attributes:

| Attribute | Description | Example |
|-----------|-------------|---------|
| `router` | Which OpenWrt AP/router sees this device | `router-office.lan` |
| `ssid` | WiFi network name (if available) | `MyNetwork_5G` |
| `ap_device` | Physical interface name on the router | `phy0-ap0` |
| `mapped_mac` | The MAC address this tracker is following | `11:22:33:44:55:66` |
| `mapping_exists` | `true` if this is an alias-based tracker, `false` if auto-created | `true` |
| `tracker_type` | Type of tracker (`alias` or `mac`) | `alias` |
| `target_source` | Where this tracker came from (`alias`, `known`, or `all`) | `alias` |
| `entity_key` | Internal identifier for this tracker | `alias_living_room_sensor` |

**How it works:**

When you have multiple routers (e.g., `router-office` and `router-kitchen`), the same device can be tracked globally:
- Entity shows `home` if the device is visible on **any** router
- `router` attribute shows which specific AP currently sees the device
- SSID is fetched via `iwinfo` directly from the AP

**Example:**

Create `/config/openwrt_ubus_aliases.yaml`:
```yaml
living_room_sensor: "11:22:33:44:55:66"
bedroom_lamp: "AA:BB:CC:DD:EE:FF"
```

You get entity `device_tracker.living_room_sensor` with attributes:
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

Security and secrets:

- `!secret` is not supported in alias mappings.
- UI mapping stores plain MAC values in config entry options.
- For strict GitOps/secret management, prefer `mapping_source = file` and manage file content via your deployment toolchain.

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
