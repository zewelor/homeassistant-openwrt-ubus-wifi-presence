# Automation examples

The entity IDs below are fictional. Replace them with the entities created in your Home Assistant instance.

## Turn on a light when a tracked device arrives

```yaml
alias: Turn on the entryway light when a tracked device arrives
triggers:
  - trigger: state
    entity_id: device_tracker.living_room_sensor
    to: "home"
actions:
  - action: light.turn_on
    target:
      entity_id: light.entryway
mode: single
```

## Notify when an SSID has no connected clients

```yaml
alias: Notify when the IoT network becomes empty
triggers:
  - trigger: state
    entity_id: binary_sensor.openwrt_wifi_iot_network_presence
    to: "off"
    for: "00:05:00"
actions:
  - action: notify.send_message
    target:
      entity_id: notify.example_device
    data:
      message: No clients have been connected to the IoT network for five minutes.
mode: single
```
