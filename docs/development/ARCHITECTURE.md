# Architecture

This document describes the architecture that is currently implemented by the
OpenWrt Ubus WiFi Presence integration.

## Scope

The integration is intentionally focused on WiFi presence:

- per-device `device_tracker` entities
- one global `binary_sensor` per observed WiFi SSID
- wireless clients reported by OpenWrt `iwinfo`
- multiple OpenWrt config entries and access points

It does not expose wired clients, router system metrics, switches, buttons, or
services.

## Source layout

```text
custom_components/openwrt_ubus/
├── __init__.py               # config-entry lifecycle
├── api/                      # ubus JSON-RPC client and exceptions
├── binary_sensor/            # global WiFi SSID presence sensors
├── config_flow.py            # Home Assistant config-flow entry point
├── config_flow_handler/      # user, reauth, reconfigure, and options flows
├── const.py                  # domain, configuration keys, defaults
├── coordinator/              # polling and tracker-target construction
├── data.py                   # runtime dataclasses and config-entry types
├── device_tracker/           # dynamic ScannerEntity platform
├── diagnostics.py            # redacted diagnostics output
├── manifest.json
├── strings.json
└── translations/
```

## Config-entry lifecycle

### Setup

`async_setup_entry()` performs the following steps:

1. Build the ubus endpoint URL from the config entry.
2. Create `OpenWrtUbusClient` with Home Assistant's shared `aiohttp` session.
3. Create `OpenWrtUbusWifiPresenceCoordinator`.
4. Reuse the global tracker and WiFi SSID managers from another entry,
   or create them for the first entry.
5. Store the client, coordinator, and shared managers in `entry.runtime_data`
   before the first asynchronous operation, so concurrent entry setup cannot
   create separate manager sets.
6. Run the first coordinator refresh.
7. Forward setup to the `device_tracker` and `binary_sensor` platforms.
8. Let `OptionsFlowWithReload` reload entries after option changes.

The remote ubus session is destroyed when the config entry unloads successfully.
Home Assistant's shared `aiohttp` session is not owned or closed by the
integration.

New config entries use the lowest valid local access-point BSSID returned by
`iwinfo.info` as their stable unique ID. Client/STA interfaces are excluded.
Connection and credential values stay in `entry.data`; tracking and polling
behavior is created in `entry.options`.

### Migration

The config-flow version is `3`. Version 0.6 deliberately has no migration from
older config-entry versions; users remove their old entries before updating and
add each router again afterward.

## Ubus API layer

`OpenWrtUbusClient` is a small asynchronous JSON-RPC client. It owns protocol
handling but does not create Home Assistant entities.

### Session handling

- `session.login` creates a ubus session.
- Session expiry is tracked locally.
- A call that fails with ubus status code 6 resets the session, authenticates
  again, and retries once.
- `session.destroy` is attempted during unload.

### Response contract

A successful ubus `call` response has a JSON-RPC `result` list containing:

1. the ubus status code
2. an optional object payload

The client validates this structure and returns the object payload as
`dict[str, Any]`. Non-object payloads are rejected as protocol errors.

### Wireless calls

The client uses:

- `network.wireless.status` to inventory configured WiFi SSIDs and map active
  wireless interfaces to them
- `uci.get` as a compatibility fallback when wireless status must be queried per
  radio device
- `iwinfo.devices` to discover wireless interfaces
- `iwinfo.assoclist` to retrieve associated stations
- `iwinfo.info` as a WiFi SSID fallback

The WiFi SSID inventory result includes a completeness flag. A global wireless
status response is complete for the configured inventory. In per-radio
compatibility mode, a failed UCI or radio-status call produces partial data with
`complete = false`. The coordinator combines that signal with the completeness
of SSID resolution through `iwinfo.info` for interfaces missing from the status
mapping. Partial data can still update client presence, but it is never
authoritative enough to delete a WiFi SSID sensor.

Transport, authentication, and ubus call errors are translated into
integration-specific exceptions.

## Coordinator

`OpenWrtUbusWifiPresenceCoordinator` polls OpenWrt at the configured scan
interval, which defaults to 30 seconds.

Each refresh:

1. Loads the effective alias mapping.
2. Builds the interface-to-WiFi-SSID mapping and configured WiFi SSID inventory.
3. Records whether the configured and observed WiFi SSID inventories were both complete.
4. Discovers interfaces exposed by `iwinfo`.
5. Fetches the association list for every interface.
6. Ignores malformed MAC addresses and stations explicitly marked
   `authorized: false`.
7. Stores currently associated stations in `coordinator.data`.
8. Rebuilds the tracker targets and known WiFi SSID set.

### Runtime station model

`coordinator.data` is a dictionary keyed by normalized MAC address. Each
`WifiPresenceDevice` contains:

- `mac`
- `ap_device`
- `ssid`
- `inactive_ms`, when reported by `iwinfo`
- `signal_dbm`, when reported by `iwinfo`

Presence is represented by membership in this current association dataset. The
integration does not enrich stations with DHCP hostname or IP address data.

### Tracker targets

Tracker targets are separate from currently associated stations. This allows an
entity to remain registered while its target is away.

Targets can come from:

- alias mappings
- MAC addresses known in Home Assistant's Device Registry
- all currently observed MAC addresses when `tracking_mode = all`

Aliases take priority over plain MAC targets for the same MAC address.

When a target no longer matches the selected tracking mode, its Entity Registry
entry is hidden and disabled by the integration rather than deleted. It can be
re-enabled automatically when the target becomes eligible again.

## Device trackers

The `device_tracker` platform registers every loaded coordinator with one
domain-level `OpenWrtUbusWifiPresenceDeviceTrackerManager`. The manager builds a
global target inventory and creates each `ScannerEntity` on one owner config
entry's platform. If that entry unloads, ownership moves to another loaded
entry without changing the global registry identity.

Tracker identity is stable:

```text
unique_id = <entity key>
```

Alias entity keys use `alias_<slug>`. Direct MAC targets use `mac_<MAC>`.
Changing the MAC behind an existing alias therefore keeps the same entity.
Legacy per-router and MAC-based unique IDs are not migrated automatically.

The manager is the tracker's only update source. A tracker reports `home` when
any successfully updated coordinator sees its target MAC. It reports
`not_home` only when every enabled config entry has a registered coordinator,
every latest update succeeded, and none sees the MAC. Otherwise it is
`unavailable`, preventing stale data from publishing a false absence.

When multiple routers report the same MAC, the manager prefers the association
with the newest effective activity time, then the strongest signal, and finally
stable router and AP ordering. The `router`, `ssid`, and `ap_device` attributes
describe that selected association.

## Global WiFi SSID presence sensors

The `binary_sensor` platform uses one domain-level
`OpenWrtUbusSsidPresenceManager` shared by all config entries.

The manager:

- registers every loaded coordinator
- creates one sensor per normalized WiFi SSID
- keeps an off sensor while its WiFi SSID is still reported with no current
  clients
- removes a stale sensor only when every enabled config entry has a registered
  coordinator, every latest update succeeded, every WiFi SSID inventory is
  complete, and none reports that WiFi SSID
- suppresses removal during failed updates, partial compatibility fallbacks,
  startup, and config-entry reloads
- aggregates associations across routers
- deduplicates the same MAC observed by more than one router

A sensor is on when at least one unique associated client is present on that
WiFi SSID. Its `connected_clients` attribute contains the aggregated
unique-client count. Permanently renaming a WiFi SSID removes the old sensor and
creates a sensor with a different stable unique ID for the new name.

Cleanup removes only `binary_sensor` Entity Registry entries using the
`openwrt_ubus` platform and matching the dedicated WiFi SSID sensor unique-ID
prefix. The registry `config_entry_id` identifies the global entity's creation
owner; it is not WiFi SSID provenance or a cleanup boundary. This prevents
unrelated entities from being affected while still handling a WiFi SSID that
disappeared while Home Assistant was offline.

Only one config entry acts as the entity-creation owner at a time. If that entry
unloads, ownership transfers to another registered entry. Unregister itself does
not prove that a WiFi SSID was deleted because it is also part of a normal config
entry reload.

The manager keeps submitted WiFi SSIDs pending until Home Assistant accepts or
rejects their entity objects. Only accepted objects are active, and a removal
callback removes a mapping only when it belongs to that exact object. The
listener-driven sensors explicitly disable entity polling.

The authoritative cleanup gate, pending/accepted lifecycle, and creation-owner
semantics are recorded in
[Architectural and Design Decisions](DECISIONS.md), with links to the final
implementation commits and Home Assistant Core 2026.8.0.

## Alias mapping

Aliases can come from:

- `file`: YAML file under the Home Assistant config directory
- `ui`: multiline YAML stored in config-entry options
- `hybrid`: combine both sources, with file entries winning slug collisions

The loader validates alias slugs and normalizes MAC addresses before returning
the effective mapping to the coordinator.

## Error handling

The coordinator maps client errors to Home Assistant lifecycle exceptions:

- authentication errors -> `ConfigEntryAuthFailed`
- communication and ubus errors -> `UpdateFailed`

Home Assistant then handles reauthentication, availability, and retry timing.
A compatibility fallback that returns useful but incomplete WiFi SSID inventory
does not fail client-presence polling; it only blocks destructive sensor cleanup.

## Diagnostics

Diagnostics include:

- redacted config-entry data
- current associated stations
- active tracking and mapping modes
- alias mapping summary
- computed tracker targets

Credentials, hosts, network addresses, alias mapping content and paths, WiFi
SSIDs, AP names, device aliases, config-entry identities, and MAC addresses are
redacted through `async_redact_data()`.

## Validation

Project validation is run through the repository scripts and CI workflows:

```bash
./script/check
./script/hassfest
```

Tests cover the API session retry behavior, coordinator error/filtering logic,
config flows, and diagnostics. Platform behavior should be covered when changing
dynamic tracker creation, cross-router lookup, or the global WiFi SSID manager.
