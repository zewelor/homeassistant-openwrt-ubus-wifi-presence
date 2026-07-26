# Architectural and Design Decisions

This document records significant architectural and design decisions made during the development of this integration.

## Format

Each decision is documented with:

- **Date:** When the decision was made
- **Context:** Why this decision was necessary
- **Decision:** What was decided
- **Rationale:** Why this approach was chosen
- **Consequences:** Expected impacts and trade-offs

---

## Decision Log

### Introduce `known_or_alias` and `all` tracking modes with alias mapping file

**Date:** 2026-03-04

**Context:** Users wanted stable tracker entities for selected devices (for example phones), the ability to repoint those entities to a new MAC over time, and a way to avoid noisy "track everything" behavior by default.

**Decision:** Add two tracking modes and alias mapping:

- `known_or_alias` (default): track aliases from YAML file and HA-known MAC devices (from device registry)
- `all`: track all observed WiFi clients
- Alias mappings come from configurable YAML file (`alias: mac`, default `openwrt_ubus_aliases.yaml`)
- Aliases have priority over plain MAC trackers to avoid duplicates for same device

**Rationale:**

- Keeps day-to-day UI clean for presence automations
- Preserves stable entity identity for aliases while allowing MAC repointing
- Still supports full visibility mode when needed for diagnostics
- Integrates with existing HA device model through device registry MAC connections

**Consequences:**

- New options added to config/options flow (`tracking_mode`, `alias_mapping_file`)
- Tracker set now depends on mode and alias file content
- Filtered-out trackers are disabled/hidden by integration instead of hard deletion
- `!secret` is intentionally not supported in alias mapping YAML in this iteration

---

### Add alias mapping source modes (`file` / `ui` / `hybrid`) for UI-first + GitOps

**Date:** 2026-03-05

**Context:** Users needed both Home Assistant UI-first setup and GitOps-friendly alias management. Previous implementation supported only file-based aliases and forced file handling even for UI-centric users.

**Decision:**

- Add `mapping_source` option with values `file`, `ui`, `hybrid` (default `hybrid`)
- Keep `alias_mapping_file` as existing file source
- Add `alias_mapping_ui` as multiline YAML source in config/options flow
- In `hybrid` mode, file mapping overrides UI mapping on alias slug collision
- Keep `!secret` unsupported in both file and UI mapping

**Rationale:**

- Supports UI-first onboarding without removing deterministic GitOps workflow
- Keeps behavior explicit per config entry via source mode
- Preserves previous file-first behavior for existing installations
- Avoids hidden secret resolution semantics in config entries

**Consequences:**

- Options flow now exposes mapping source + UI YAML field
- Alias loader resolves and merges multiple sources depending on mode
- Diagnostics include mapping source and per-source mapping counts
- For strict GitOps users, recommended mode is `file`

---

### Use Strict ScannerEntity Pattern for Wi-Fi Presence Trackers

**Date:** 2026-03-04

**Context:** The integration tracks Wi-Fi presence only (`home` / `not_home`). Home Assistant's current device tracker architecture treats router-based trackers as scanner entities, and one physical device can be represented across multiple integrations through shared identifiers/connections.

**Decision:** Implement trackers as strict `ScannerEntity` without custom `device_info`, keep focus on presence-only
states, and explicitly declare `SourceType.ROUTER`.

**Rationale:**

- Aligns with current Home Assistant device tracker expectations for router/scanner integrations
- Avoids creating redundant per-client device entries inside this integration
- Preserves compatibility with HA's cross-integration device linking model (same MAC can be associated from other integrations)
- Keeps this fork intentionally minimal: Wi-Fi presence only, no extra sensor/device modeling
- Makes the router-source contract visible even though
  [`ScannerEntity` defaults to `SourceType.ROUTER`](https://github.com/home-assistant/core/blob/2026.6.0/homeassistant/components/device_tracker/entity.py)
  in the minimum supported Home Assistant release

**Consequences:**

- The integration page may show mainly hub + tracker entities instead of a long per-client device list
- Existing users migrating from earlier fork versions that created client devices need cleanup; this integration performs automatic cleanup of legacy device entries
- Presence logic remains unchanged (`home` / `not_home`)

---

### Require authoritative inventory before deleting WiFi SSID entities

**Date:** 2026-07-26

**Context:** A successful coordinator update can still contain partial compatibility data. Treating any successful update
as proof that a WiFi SSID was deleted could remove a valid Entity Registry entry.

**Decision:** Delete only when at least one OpenWrt entry is enabled, every enabled entry has a registered successful
coordinator, every coordinator reports `ssid_inventory_complete`, and the WiFi SSID is absent from their union. Cleanup
is restricted to `binary_sensor` entries from `openwrt_ubus` with the dedicated WiFi SSID unique-ID prefix.

**Rationale:**

- Failed, missing, startup, reload, and partial-fallback data cannot prove absence
- A successful empty global wireless inventory remains authoritative
- The domain, platform, and prefix boundary protects unrelated registry entries

**Consequences:**

- Stale sensors remain during incomplete refreshes
- Permanent rename or deletion removes the old sensor after an authoritative refresh
- The contract is implemented and tested in
  [the final cleanup commit](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/tree/7a01856bfa3fc98ac2ca4206971ad81b5d70c7e0)

---

### Track pending and accepted WiFi SSID entity objects separately

**Date:** 2026-07-26

**Context:** Passing an entity to Home Assistant's add callback only schedules processing. Home Assistant can reject a
disabled entity, and delayed removal callbacks can arrive after a replacement was created.

**Decision:** Keep pending WiFi SSIDs separate from entities accepted through `async_added_to_hass()`. Clear pending state
for accepted and rejected additions, and remove an active mapping only when the callback belongs to the exact stored
object. Listener-driven WiFi SSID entities explicitly set `_attr_should_poll = False`.

**Rationale:**

- Prevents duplicate scheduling while Home Assistant decides whether to accept an entity
- Prevents a late callback from deleting a replacement object
- Avoids an EntityPlatform polling timer in addition to coordinator listener updates

**Consequences:**

- Entity lifecycle state follows Home Assistant acceptance rather than callback submission
- Disabled entries and owner transfer are verified through real `EntityPlatform` instances
- The contract is implemented and tested in
  [the final lifecycle commit](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/tree/3055c7b4c8dac0c554987ab5dec5f4d0bae4b8cf)

---

### Treat `config_entry_id` as creation ownership, not WiFi SSID provenance

**Date:** 2026-07-26

**Context:** WiFi SSID sensors are global across enabled routers, but Home Assistant requires one config entry and
EntityPlatform to create each registry identity.

**Decision:** Use `config_entry_id` only as the current creation owner. Do not use it to decide which router reported a
WiFi SSID or whether a global sensor is stale. Transfer ownership only after the old platform removes its entity object.

**Rationale:**

- The same WiFi SSID can be reported by multiple routers
- Registry ownership can move without changing the global entity identity
- Waiting for platform removal avoids overlapping live objects

**Consequences:**

- Cleanup scans the dedicated global identity boundary instead of one owner's entries
- User and integration disabling are preserved across ownership changes
- Config-entry disabling is reconciled by Home Assistant when ownership moves to an enabled entry

These decisions are grounded in
[Home Assistant Core 2026.6.0](https://github.com/home-assistant/core/tree/2026.6.0) and the immutable integration commits
linked above.

---

### Use DataUpdateCoordinator for All Data Fetching

**Date:** 2025-11-29 (Template initialization)

**Context:** The integration needs to fetch data from an external API and share it with multiple entities. Home Assistant provides several patterns for this.

**Decision:** Use `DataUpdateCoordinator` from `homeassistant.helpers.update_coordinator` as the central data management component.

**Rationale:**

- Provides built-in support for update intervals and error handling
- Automatic retry with exponential backoff
- Shared data access prevents duplicate API calls
- Standard pattern recommended by Home Assistant
- Entities automatically become unavailable when coordinator fails

**Consequences:**

- Single update interval applies to all entities
- Data is fetched even if no entities are enabled
- Device trackers use the integration's coordinator entity base
- Global WiFi SSID sensors consume shared coordinator data through their domain-level manager and listener callbacks

---

### Separate API Client from Coordinator

**Date:** 2025-11-29 (Template initialization)

**Context:** The coordinator needs to fetch data, but business logic should be separated from data transport.

**Decision:** Implement API communication in separate `api/client.py` module, coordinator only orchestrates updates.

**Rationale:**

- Separation of concerns: transport vs. orchestration
- Easier to test API client in isolation
- Simpler to swap API implementation if needed
- Clearer error handling boundaries

**Consequences:**

- Additional abstraction layer
- Coordinator depends on API client
- API client raises custom exceptions for error translation

---

### Platform-Specific Directories

**Date:** 2025-11-29 (Template initialization)

**Context:** The integration supports `device_tracker` and `binary_sensor` platforms with different lifecycle needs.

**Decision:** Keep each supported platform in its own package.

**Rationale:**

- Clear organization as integration grows
- Easier to find specific entity implementations
- Keeps tracker and global WiFi SSID sensor lifecycle code separate
- Follows Home Assistant Core pattern

**Consequences:**

- Platform `__init__.py` must import and register entities

---

## Future Considerations

### Polling vs. Push

**Status:** Uses polling

Currently implements polling-based updates. If the API supports webhooks or WebSocket, consider implementing push-based updates for real-time responsiveness.

---

## Decision Review

These decisions should be reviewed periodically (suggested: quarterly or when major features are added) to ensure they still serve the integration's needs.

---

### Separate `reauth`, `reconfigure`, and `options` flows while keeping host-based identity

**Date:** 2026-03-05

**Context:** Authentication failures and connection changes were previously handled through OptionsFlow updates to entry data. This mixed concerns and did not provide Home Assistant-standard reauth behavior.

**Decision:**

- Raise `ConfigEntryAuthFailed` from coordinator when credentials are invalid
- Implement dedicated `reauth` step for credential recovery
- Implement dedicated `reconfigure` step for connection parameters
- Keep `options` for runtime behavior only (tracking mode, alias file, backends, scan interval)
- Keep `host` immutable post-setup in current architecture

**Rationale:**

- Aligns integration behavior with current Home Assistant config-entry lifecycle
- Prevents silent retry loops on invalid credentials
- Reduces accidental identity churn by avoiding host edits after setup

**Consequences:**

- New flows visible in HA UI (`reauth`, `reconfigure`)
- Existing users can change credentials/connection settings without remove+add
- Host rename is intentionally out of scope for now
