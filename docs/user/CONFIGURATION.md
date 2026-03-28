# Configuration Reference

This integration is configured from the Home Assistant UI.

## Setup and management paths

- Add integration: Settings -> Devices & Services -> Add Integration
- Reauthenticate: triggered when credentials are invalid
- Reconfigure: update connection settings (host is fixed)
- Options: update tracking behavior and polling settings

## Setup fields (`user` step)

| Field | Type | Default | Description |
|---|---|---|---|
| `host` | string | - | Stable router host identifier for this entry |
| `ip_address` | string | empty | Optional direct IP for ubus URL |
| `use_https` | bool | `false` | Use HTTPS instead of HTTP |
| `port` | int | scheme default | Optional custom port |
| `verify_ssl` | bool | `false` | Verify TLS certificate |
| `endpoint` | string | `ubus` | ubus RPC endpoint path |
| `username` | string | - | OpenWrt username |
| `password` | string | - | OpenWrt password |
| `tracking_mode` | enum | `known_or_alias` | `known_or_alias` or `all` |
| `alias_mapping_file` | string | `openwrt_ubus_aliases.yaml` | YAML file with alias->MAC mapping |
| `mapping_source` | enum | `hybrid` | Alias source: `file`, `ui`, `hybrid` |
| `alias_mapping_ui` | string | empty | Multiline YAML alias->MAC mapping stored in options/data |
| `wireless_software` | enum | `iwinfo` | Wireless backend: `iwinfo` or `hostapd` |
| `scan_interval` | int | `30` | Poll interval in seconds (10-300) |

## Reconfigure fields (`reconfigure` step)

`host` is intentionally not editable post-setup.

| Field | Type | Description |
|---|---|---|
| `ip_address` | string | Optional direct IP override |
| `use_https` | bool | Switch HTTP/HTTPS |
| `port` | int | Custom port override |
| `verify_ssl` | bool | TLS verification |
| `endpoint` | string | ubus path |
| `username` | string | Connection username |
| `password` | string | Connection password |

## Options fields (`options` step)

| Field | Type | Default | Description |
|---|---|---|---|
| `tracking_mode` | enum | `known_or_alias` | Presence scope mode |
| `alias_mapping_file` | string | `openwrt_ubus_aliases.yaml` | Alias file path |
| `mapping_source` | enum | `hybrid` | Alias source selection (`file`, `ui`, `hybrid`) |
| `alias_mapping_ui` | string | empty | Multiline YAML alias mapping from UI |
| `wireless_software` | enum | `iwinfo` | Wireless backend |
| `scan_interval` | int | `30` | Polling interval |

## Tracking modes

### `known_or_alias` (default)

- Creates alias trackers from mapping file.
- Creates MAC trackers only for HA-known devices (device registry MAC connection).
- Filters unknown/non-aliased devices.

### `all`

- Creates trackers for all observed WiFi clients.
- Alias entries still take priority.
- For aliased MACs, only alias entity is kept.

## Alias mapping file

Path is resolved relative to `/config` unless absolute.

Example `/config/openwrt_ubus_aliases.yaml`:

```yaml
my_phone: "AA:BB:CC:DD:EE:FF"
someones_phone: "11:22:33:44:55:66"
```

Rules:

- Top-level must be a YAML object.
- Format is strictly `alias: mac`.
- Invalid rows are skipped and logged.
- `!secret` tags are not supported in this file in current version.

## Alias mapping source modes

- `file`: use only `alias_mapping_file`.
- `ui`: use only `alias_mapping_ui`.
- `hybrid` (default): use both, and file overrides UI on alias slug collision.

## Alias mapping UI format

`alias_mapping_ui` uses the same YAML shape as file mapping:

```yaml
my_phone: "AA:BB:CC:DD:EE:FF"
someones_phone: "11:22:33:44:55:66"
```

Rules:

- Must be valid YAML object (`alias: mac`).
- Invalid UI YAML is rejected by options form.
- `!secret` is not supported.
- UI values are stored directly in config entry options.

## Entity lifecycle behavior

- Alias entities are auto-created; no manual per-MAC enable required.
- Changing MAC under the same alias keeps alias entity identity.
- Filtered entities are disabled/hidden by integration (not deleted).
- Returning to broader mode can re-enable entities previously disabled by integration.
