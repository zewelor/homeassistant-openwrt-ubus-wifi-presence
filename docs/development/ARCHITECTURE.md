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
├── __init__.py               # config-entry lifecycle and migration
├── api/                      # ubus JSON-RPC client and exceptions
├── binary_sensor/            # global WiFi SSID presence sensors
├── config_flow.py            # Home Assistant config-flow entry point
├── config_flow_handler/      # user, reauth, reconfigure, and options flows
├── const.py                  # domain, configuration keys, defaults
├── coordinator/              # polling and tracker-target construction
├── data.py                   # runtime dataclasses and config-entry types
├── device_tracker/           # dynamic ScannerEntity platform
├── diagnostics.py            # redacted diagnostics output
├── entity/                   # shared coordinator-entity base
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
4. Run the first coordinator refresh.
5. Store the client and coordinator in `entry.runtime_data`.
6. Forward setup to the `device_tracker` and `binary_sensor` platforms.
7. Register an update listener that reloads the entry after option changes.

The remote ubus session is destroyed when the config entry unloads successfully.
Home Assistant's shared `aiohttp` session is not owned or closed by the
integration.

### Migration

The config-flow version is `2`.

When Home Assistant migrates a version-1 config entry, `async_migrate_entry()`
removes legacy per-client Device Registry entries created before the integration
moved to scanner-based trackers. The entry is then updated to version 2, so the
cleanup runs once instead of during every setup.

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
status response is complete. In per-radio compatibility mode, a failed UCI or
radio-status call produces partial data with `complete = false`. Partial data can
still update client presence, but it is never authoritative enough to delete a
WiFi SSID sensor.

Transport, authentication, and ubus call errors are translated into
integration-specific exceptions.

## Coordinator

`OpenWrtUbusWifiPresenceCoordinator` polls OpenWrt at the configured scan
interval, which defaults to 30 seconds.

Each refresh:

1. Loads the effective alias mapping.
2. Builds the interface-to-WiFi-SSID mapping and configured WiFi SSID inventory.
3. Records whether that WiFi SSID inventory was complete.
4. Discovers `iwinfo` access-point interfaces.
5. Fetches the association list for every interface.
6. Ignores malformed MAC addresses and stations explicitly marked
   `authorized: false`.
7. Stores currently associated stations in `coordinator.data`.
8. Rebuilds the tracker targets and known WiFi SSID set.

### Runtime station model

`coordinator.data` is a dictionary keyed by normalized MAC address. Each
`WifiPresenceDevice` contains only:

- `mac`
- `ap_device`
- `ssid`

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

The `device_tracker` platform creates `ScannerEntity` instances dynamically from
`coordinator.tracker_targets`.

Tracker identity is stable:

```text
unique_id = <configured host>_<entity key>
```

Alias entity keys use `alias_<slug>`. Direct MAC targets use `mac_<MAC>`.
Changing the MAC behind an existing alias therefore keeps the same entity.

For state resolution, a tracker checks its own coordinator first and then all
other loaded `openwrt_ubus` coordinators. Consequently, a tracker reports
`home` when its target MAC is associated with any configured OpenWrt router. The
`router`, `ssid`, and `ap_device` attributes describe the matching association,
including the WiFi SSID reported for it.

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
implementation commits and Home Assistant Core 2026.6.0.

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

Credentials, hosts, network addresses, alias mapping content, and MAC addresses
are redacted through `async_redact_data()`.

## Validation

Project validation is run through the repository scripts and CI workflows:

```bash
./script/check
./script/hassfest
```

Tests cover the API session retry behavior, coordinator error/filtering logic,
config flows, and diagnostics. Platform behavior should be covered when changing
dynamic tracker creation, cross-router lookup, or the global WiFi SSID manager.
