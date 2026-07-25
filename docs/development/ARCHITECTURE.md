# Architecture Overview

This document describes the current architecture of the OpenWrt Ubus WiFi Presence
custom integration. It intentionally documents only code that exists in this
repository.

## Scope

The integration has two runtime responsibilities:

1. Track whether selected WiFi clients are associated with any configured OpenWrt
   access point.
2. Expose one global binary sensor per discovered SSID, indicating whether at least
   one client is associated with that SSID.

It does not collect wired clients, DHCP leases, hostnames, client IP addresses,
system metrics, modem data, or router controls.

## Source Layout

```text
custom_components/openwrt_ubus/
├── __init__.py
├── api/
│   ├── __init__.py
│   └── client.py
├── binary_sensor/
│   └── __init__.py
├── config_flow.py
├── config_flow_handler/
│   ├── __init__.py
│   └── handler.py
├── const.py
├── coordinator/
│   ├── __init__.py
│   └── wifi_presence.py
├── data.py
├── device_tracker/
│   ├── __init__.py
│   └── wifi_device.py
├── diagnostics.py
├── entity/
│   ├── __init__.py
│   └── base.py
├── manifest.json
├── strings.json
├── translations/
│   └── en.json
└── utils/
    └── alias_mapping.py
```

## Setup and Config Entry Lifecycle

`__init__.py` owns the Home Assistant config entry lifecycle:

1. Build the ubus HTTP endpoint from the config entry.
2. Reuse Home Assistant's shared `aiohttp.ClientSession`.
3. Create `OpenWrtUbusClient`.
4. Create `OpenWrtUbusWifiPresenceCoordinator`.
5. Perform the first coordinator refresh.
6. Store the client and coordinator in `entry.runtime_data`.
7. Forward setup to `device_tracker` and `binary_sensor`.
8. Close the remote ubus session when the entry unloads.

Config entry version `2` contains a one-time migration from version `1`. The
migration removes legacy per-client Home Assistant device-registry entries created
before the integration switched to scanner-style device trackers. This cleanup is
not part of normal startup.

## Ubus API Client

`api/client.py` implements the minimal JSON-RPC client required by this integration.
It handles:

- login and remote session expiry;
- one reconnect-and-retry after an authentication/session failure;
- request timeout and HTTP errors;
- ubus status-code validation;
- OpenWrt compatibility for `network.wireless.status`;
- the `iwinfo` methods used by the coordinator.

The HTTP JSON-RPC response for a successful ubus call has the following outer
shape:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": [0, {"payload": "value"}]
}
```

`OpenWrtUbusClient.call()` validates that envelope and returns the payload object.
For `iwinfo.assoclist`, `rpcd-mod-iwinfo` places associated station objects in the
payload's `results` array:

```json
{
  "results": [
    {
      "mac": "AA:BB:CC:DD:EE:FF",
      "authorized": true,
      "signal": -52
    }
  ]
}
```

The client therefore expects an object containing `results`; a bare list is not a
supported rpcd response shape.

Relevant OpenWrt references:

- <https://openwrt.org/docs/techref/ubus>
- <https://openwrt.org/docs/guide-developer/ubus/iwinfo>
- <https://lxr.openwrt.org/source/rpcd/iwinfo.c>

## Coordinator

`coordinator/wifi_presence.py` is the only layer that polls the router and converts
raw ubus data into integration data.

The update interval comes from `scan_interval` and defaults to 30 seconds.
Each refresh performs the following work:

1. Refresh alias mappings.
2. Obtain interface-to-SSID information from `network.wireless.status`.
3. List wireless interfaces through `iwinfo.devices`.
4. Call `iwinfo.assoclist` for every interface.
5. Ignore stations explicitly reported with `authorized: false`.
6. Normalize MAC addresses.
7. Build the current associated-station dataset.
8. Read known MAC addresses and names from the Home Assistant device registry.
9. Rebuild the desired tracker targets for the configured tracking mode.

### Coordinator Data Contract

`coordinator.data` is a dictionary keyed by normalized MAC address:

```python
{
    "AA:BB:CC:DD:EE:FF": WifiPresenceDevice(
        mac="AA:BB:CC:DD:EE:FF",
        ap_device="phy0-ap0",
        ssid="Home",
    )
}
```

Every item represents a station currently associated with that router. Absence from
the dictionary means the station is not currently associated. The model deliberately
does not contain a redundant `connected` flag or DHCP-derived fields.

### Known SSIDs

The coordinator also stores SSIDs discovered from wireless interface status. This
allows an SSID binary sensor to exist even when it currently has zero associated
clients.

### Error Mapping

- Authentication failures become `ConfigEntryAuthFailed`, which starts Home
  Assistant's reauthentication flow.
- Communication and other ubus client failures become `UpdateFailed`, allowing the
  coordinator to retain Home Assistant's normal retry and availability behavior.

## Alias Mapping and Tracker Targets

`utils/alias_mapping.py` loads alias-to-MAC mappings from:

- a file in the Home Assistant configuration directory;
- YAML stored in config entry options;
- both sources in `hybrid` mode, where the file wins on slug collisions.

The coordinator separates current station data from desired tracker entities by
building `TrackerTarget` objects.

This separation is important:

- an alias tracker remains registered when its device is away;
- a known device remains available as `not_home` when it is absent from the current
  station dataset;
- changing an alias MAC keeps the alias entity's stable entity key;
- filtering modes can disable or re-enable existing registry entries without
  deleting them.

Tracking modes:

- `known_or_alias`: aliases plus MAC addresses known to the Home Assistant device
  registry;
- `all`: aliases plus every currently observed MAC address.

## Device Tracker Platform

`device_tracker/__init__.py` synchronizes desired tracker targets with the Home
Assistant entity registry and creates missing scanner entities.

Entries excluded by the active tracking mode are hidden and disabled by the
integration rather than deleted. User-disabled entities remain under user control.

`device_tracker/wifi_device.py` implements each `ScannerEntity`.

For every state read it:

1. resolves the current MAC from the tracker target or stable entity key;
2. checks the local coordinator first;
3. checks other loaded OpenWrt Ubus config entries;
4. reports `home` when any router currently sees the MAC;
5. exposes the router, SSID, AP interface, mapping source, and mapping metadata as
   state attributes.

The unique ID combines the stable configured host and entity key:

```text
<host>_<entity-key>
```

## SSID Binary Sensor Platform

`binary_sensor/__init__.py` maintains one integration-wide
`OpenWrtUbusSsidPresenceManager` in `hass.data`.

Every loaded config entry registers its coordinator with the manager. The manager:

- combines fresh data from all loaded routers;
- creates one binary sensor for each discovered SSID;
- deduplicates clients by MAC across routers;
- reports the number of associated clients as `connected_clients`;
- marks sensors unavailable unless every registered coordinator's latest update was
  successful.

A single config entry acts as the entity owner so multiple routers do not create
duplicate SSID entities.

## Config Flow

`config_flow.py` is Home Assistant's discovery entry point and exports the flow
implemented in `config_flow_handler/handler.py`.

The handler provides:

- initial setup and connection validation;
- reauthentication for changed credentials;
- reconfiguration of connection parameters except the stable `host` identity;
- options for tracking mode, alias sources, mappings, and scan interval.

The config flow version must remain synchronized with migrations in `__init__.py`.

## Diagnostics

`diagnostics.py` exposes:

- redacted config entry data;
- currently associated station records;
- tracking and mapping configuration summaries;
- desired tracker targets.

Credentials, host/IP details, aliases stored in the UI, and MAC addresses are
redacted through `async_redact_data()`.

## Design Invariants

Changes should preserve these rules:

1. Entities never call OpenWrt directly.
2. The coordinator is the only polling and transformation layer.
3. `coordinator.data` contains only currently associated stations.
4. Persistent tracker intent lives in `tracker_targets`, not in stale station data.
5. The same MAC is considered home when any loaded router sees it.
6. SSID client counts deduplicate MAC addresses across routers.
7. Alias entity keys stay stable when their mapped MAC changes.
8. Config entry migrations run once and are not repeated during every setup.

## Testing

The test suite covers config flows, coordinator error handling and station filtering,
client session recovery, diagnostics redaction, and supporting utilities.

Before merging changes, run:

```bash
./script/check
./script/test
./script/hassfest
```
