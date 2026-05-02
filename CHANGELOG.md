# Changelog

## [0.5.0](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/compare/v0.4.2...v0.5.0) (2026-05-02)


### ⚠ BREAKING CHANGES

* Entity IDs will change for existing installations. Users with automations or dashboards referencing entity IDs will need to update them.
* removes temporary custom_components/openwrt_ubus_wifi_presence shim; repository now ships only custom_components/openwrt_ubus. Bumps version to 0.2.2.
* integration domain changed from openwrt_ubus_wifi_presence to openwrt_ubus; existing entries must be re-added.

### Features

* add alias mapping and tracking modes for device_tracker ([fada41c](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/fada41c737928024adeea57af17a1169cc66f3e2))
* add reauth/reconfigure flows and dead-code checks ([052d5f5](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/052d5f5d1296da4442b126968b2fe3659a69c30c))
* add SSID presence binary sensor platform ([f20dfaa](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/f20dfaa4caad6e43eff3f9c06bba3a8d4773b5f9))
* initialize openwrt ubus wifi presence integration fork ([00c76f1](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/00c76f1b6d07447bc4e16c652201510b89c0cd74))
* rename integration domain to openwrt_ubus ([a446e3e](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/a446e3ea2cd5a7dee658283b2c58a4d1b8560081))
* show router host in reauth dialog ([de5773d](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/de5773d970d0ea5b5a3ac26270f50b2980d89f57))


### Bug Fixes

* add HACS transition shim after domain rename ([de59c16](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/de59c1648c2b4f770d3864f7794badc73fa37789))
* auto-merge pip patch/minor dependabot updates ([a26601f](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/a26601f14e20cfa17de2751320c112c35d988295))
* avoid dependabot auto-merge self-check deadlock ([0628a99](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/0628a996a6e4e04094562df3bb7f492ec4e1d02f))
* handle ubus error code 2 in per-device wireless status calls ([db2ecb6](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/db2ecb621678656ac33b0703dfe729b580040bb7))
* include router host in entity_id to avoid duplicates with multiple routers ([373a731](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/373a73188dd2c62da9417910866a9c86a608d607))
* make tag workflow idempotent when tag already exists ([bc87a45](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/bc87a4561b6bcd9fbe645f849cd7f073c2792483))
* merge device_tracker entities across multiple routers via mac_address ([af7cd9e](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/af7cd9e4d5a45a624e27dc549a7e9f2a784a52fb))
* prevent duplicate device_tracker entities in multi-router setups ([8637a5b](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/8637a5b68e6091ecbe0e325aaf5364c5703703f7))
* probe wireless status capabilities for OpenWrt 25.x ([df5e3b6](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/df5e3b6c380542ab894a2285860ecbf30e6124e7))
* resolve lint issues in wifi presence integration ([0f9c01e](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/0f9c01e87bf7ddc9d2d03a2037de655e40430398))
* run dependabot auto-merge for dependabot PR author ([76ac6bd](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/76ac6bd62041bc45efec9a36844f6021f6c5f3e8))


### Code Refactoring

* remove legacy compatibility component path ([96ce247](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/96ce2471f32104f16c2aea9b7ed83c829d83ec55))

## [0.4.2](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/compare/v0.4.1...v0.4.2) (2026-05-02)


### Features

* add SSID presence binary sensor platform ([f20dfaa](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/f20dfaa4caad6e43eff3f9c06bba3a8d4773b5f9))
