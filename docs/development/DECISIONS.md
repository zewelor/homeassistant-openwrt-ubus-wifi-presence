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

### Use Strict ScannerEntity Pattern for Wi-Fi Presence Trackers

**Date:** 2026-03-04

**Context:** The integration tracks Wi-Fi presence only (`home` / `not_home`). Home Assistant's current device tracker architecture treats router-based trackers as scanner entities, and one physical device can be represented across multiple integrations through shared identifiers/connections.

**Decision:** Implement trackers as strict `ScannerEntity` without custom `device_info` and keep focus on presence-only states.

**Rationale:**

- Aligns with current Home Assistant device tracker expectations for router/scanner integrations
- Avoids creating redundant per-client device entries inside this integration
- Preserves compatibility with HA's cross-integration device linking model (same MAC can be associated from other integrations)
- Keeps this fork intentionally minimal: Wi-Fi presence only, no extra sensor/device modeling

**Consequences:**

- The integration page may show mainly hub + tracker entities instead of a long per-client device list
- Existing users migrating from earlier fork versions that created client devices need cleanup; this integration performs automatic cleanup of legacy device entries
- Presence logic remains unchanged (`home` / `not_home`)

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

- All entities must inherit from `CoordinatorEntity`
- Single update interval applies to all entities
- Data is fetched even if no entities are enabled
- Coordinator manages entity lifecycle and availability

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

**Context:** Integration supports multiple platforms (sensor, binary_sensor, switch, etc.).

**Decision:** Each platform gets its own directory with individual entity files.

**Rationale:**

- Clear organization as integration grows
- Easier to find specific entity implementations
- Supports multiple entities per platform cleanly
- Follows Home Assistant Core pattern

**Consequences:**

- More files/directories than single-file approach
- Platform `__init__.py` must import and register entities
- Slightly more initial setup overhead

---

### EntityDescription for Static Metadata

**Date:** 2025-11-29 (Template initialization)

**Context:** Entities have static metadata (name, icon, device class) that doesn't change.

**Decision:** Use `EntityDescription` dataclasses to define static entity metadata.

**Rationale:**

- Declarative and easy to read
- Type-safe with dataclasses
- Recommended Home Assistant pattern
- Separates static configuration from dynamic behavior

**Consequences:**

- Each entity type needs an EntityDescription
- Dynamic entities need custom handling
- Static and dynamic properties clearly separated

---

## Future Considerations

### State Restoration

**Status:** Not yet implemented

Consider implementing state restoration for switches and configurable settings to maintain state across Home Assistant restarts when the external device is unavailable.

### Multi-Device Support

**Status:** Not yet implemented

Current architecture assumes single device per config entry. If multi-device support is needed, coordinator data structure will need redesign to map device ID → data.

### Polling vs. Push

**Status:** Uses polling

Currently implements polling-based updates. If the API supports webhooks or WebSocket, consider implementing push-based updates for real-time responsiveness.

---

## Decision Review

These decisions should be reviewed periodically (suggested: quarterly or when major features are added) to ensure they still serve the integration's needs.
