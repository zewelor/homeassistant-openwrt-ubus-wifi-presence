# Configuration Reference

This integration is configured from the Home Assistant UI.

## Where to configure

1. Go to **Settings** -> **Devices & Services**.
2. Select **OpenWrt Ubus WiFi Presence**.
3. Click **Configure**.

## Options

| Option | Type | Default | Description |
|---|---|---|---|
| `host` | string | - | Router hostname used for connection and unique host scope |
| `ip_address` | string | empty | Optional direct IP for ubus endpoint URL |
| `use_https` | bool | `false` | Use HTTPS instead of HTTP |
| `port` | int | scheme default | Optional custom port |
| `verify_ssl` | bool | `false` | Verify TLS certificate |
| `endpoint` | string | `ubus` | ubus RPC endpoint path |
| `username` | string | - | OpenWrt username |
| `password` | string | - | OpenWrt password |
| `wireless_software` | enum | `iwinfo` | Wireless backend: `iwinfo` or `hostapd` |
| `dhcp_software` | enum | `dnsmasq` | DHCP source: `dnsmasq`, `odhcpd`, `ethers`, `none` |
| `scan_interval` | int | `30` | Poll interval in seconds (10-300) |
| `tracking_mode` | enum | `known_or_alias` | `known_or_alias` or `all` |
| `alias_mapping_file` | string | `openwrt_ubus_aliases.yaml` | YAML file with alias->MAC mapping |

## Tracking modes

### `known_or_alias` (default)

- Creates tracker entities for aliases from mapping file.
- Creates MAC tracker entities only for devices known in HA device registry (`mac` connection).
- Unknown/non-aliased/non-known clients are filtered out.

### `all`

- Creates tracker entities for all observed WiFi clients.
- Alias entries still apply and take priority.
- For aliased MACs, only alias entity is kept.

## Alias mapping file

Path is resolved relative to `/config` unless absolute.

Example `/config/openwrt_ubus_aliases.yaml`:

```yaml
moj_phone: "AA:BB:CC:DD:EE:FF"
someones_phone: "11:22:33:44:55:66"
```

Rules:

- Top-level must be a YAML object.
- Format is strictly `alias: mac`.
- Invalid rows are skipped and logged.
- `!secret` tags are not supported in this file in current version.

## Entity lifecycle behavior

- Alias entities are auto-created; you do not need to enable matching per-MAC entities.
- Changing MAC under the same alias keeps the alias entity identity and repoints tracking.
- When mode/filter excludes an entity, integration disables and hides it (instead of deleting).
- Returning to a broader mode can re-enable entities previously disabled by integration.
