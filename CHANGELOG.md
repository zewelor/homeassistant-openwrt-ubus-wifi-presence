# Changelog

## [0.5.1](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/compare/v0.5.0...v0.5.1) (2026-07-24)


### Bug Fixes

* restore explicit SourceType.ROUTER on device tracker entity ([4c62b1f](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/4c62b1f04e4e2d0ede80c6607e3fa068f98595bc))

## [0.5.0](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/compare/v0.4.8...v0.5.0) (2026-07-24)


### ⚠ BREAKING CHANGES

* Entity IDs will change for existing installations. Users with automations or dashboards referencing entity IDs will need to update them.
* removes temporary custom_components/openwrt_ubus_wifi_presence shim; repository now ships only custom_components/openwrt_ubus. Bumps version to 0.2.2.
* integration domain changed from openwrt_ubus_wifi_presence to openwrt_ubus; existing entries must be re-added.

### Features

* add alias mapping and tracking modes for device_tracker ([fada41c](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/fada41c737928024adeea57af17a1169cc66f3e2))
* add migration guide for existing HACS integrations and update template sync ignore ([5770ade](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/5770adecb714a5751bbb8fcd70ad76a8d9277a3f))
* add reauth/reconfigure flows and dead-code checks ([052d5f5](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/052d5f5d1296da4442b126968b2fe3659a69c30c))
* add resilient download helper and integrate into setup scripts ([33e8a23](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/33e8a23f053beae58287b97765f823574fbf7fe8))
* add shfmt installation step to lint workflow and remove unnecessary workflows permission from template sync ([be79477](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/be794779d15845f645e721f1b27690d5b4b4a689))
* add SSID presence binary sensor platform ([f20dfaa](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/f20dfaa4caad6e43eff3f9c06bba3a8d4773b5f9))
* add user extensibility layer and template sync infrastructure ([d0f08cd](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/d0f08cd1452b32ec6297a1c19eba1f76f2afe5f8))
* **bootstrap:** conditionally install pre-commit hooks based on environment ([25626d6](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/25626d6b7760a3aa80c1e35a75eb40c56c6b33c6))
* **bootstrap:** update pre-commit hook installation logic for GitHub Actions ([cc39641](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/cc39641717ee3c308131e86106a742ecc8b1b3bc))
* **config-flow:** update documentation URL in user step ([dbac5b1](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/dbac5b10a283e7f239ea3e9449bf2e853f604a19))
* **config:** add config schema for integration and enhance error descriptions ([74c1420](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/74c1420baf5183bfb3fca948a59bb72ce92545a4))
* **coordinator:** implement data update coordinator with error handling and event listeners ([5133d2a](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/5133d2a4168bbc790db7c840195012ebd5765666))
* **copilot:** add GitHub Copilot Coding Agent setup workflow and update README instructions ([4958503](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/49585031efdc9178e32f4456a8249d7cd53eb573))
* **devcontainer:** add version sync script and workflow ([bb4e499](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/bb4e499311b73b4efdeac8b578a69fd5138b7355))
* **devcontainer:** expose npm binaries on PATH for AI agents ([59d690a](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/59d690ac1a83a49a6d1ba0ecb6d3decae9f0e89e))
* **devcontainer:** mount host gh CLI config for automatic auth ([31a4e1f](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/31a4e1f0e0512fa9013d8f87a35f44e46e6fbe89))
* **docs:** add comprehensive documentation for GitHub Copilot Coding Agent usage and testing ([10d4986](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/10d498678c668a01619dad31298faa16dfdc3b40))
* **docs:** add hassfest validation instructions and local validation script ([65b5bdd](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/65b5bdd5f203bda60da2a744312f6c7e88b8d3be))
* **docs:** enhance JSON formatting guidelines in translation instructions ([f0b09c3](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/f0b09c34a9441c5423b3c4db80c7aa57864fdd00))
* **docs:** update package structure guidelines and restrictions in Copilot and AGENTS documentation ([807e4d1](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/807e4d1a4f6fdc84a2999fd29ba066bc0bd1a5e2))
* **docs:** update translation instructions to clarify JSON formatting rules and placeholder usage ([cd0e1c3](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/cd0e1c3fafc0ac5b25c40beab17ac97407141b62))
* enhance Home Assistant version resolution and update setup scripts ([b06acec](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/b06acec6539bc42594e97600f4888562c13934d9))
* **entity:** add base entity class for ha_integration_domain with common functionality ([3dcb6ef](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/3dcb6ef851082dea66775894986068c9cbe787e0))
* **github:** add CODEOWNERS and auto-assign workflow ([f88df98](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/f88df986f0adc018fa14abdd087233674d6553f5))
* **gitignore:** enhance pruning logic to handle wildcard patterns and add hardcoded exclusions ([849d939](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/849d939d5e029862f6c9d28ba6f0c009fe4f448b))
* initial blueprint with modern Home Assistant patterns ([9625887](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/962588737809505c578d7cd0ae2d17b99ffe71fc))
* initialize openwrt ubus wifi presence integration fork ([00c76f1](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/00c76f1b6d07447bc4e16c652201510b89c0cd74))
* **initialize:** add parsing of .gitignore for prune paths and negations ([72b50c0](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/72b50c0c260aa44a62f63fc72475c086e128e58d))
* **initialize:** enhance repository handling in initialization script ([a7485e3](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/a7485e3e80aec42420af09d150283411eb013ac6))
* **pre-commit:** enhance Ruff and Codespell hooks for better virtual environment handling ([e3791ea](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/e3791ea263dc0e4b120ae13b99bb0d3a8c6861b5))
* rename integration domain to openwrt_ubus ([a446e3e](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/a446e3ea2cd5a7dee658283b2c58a4d1b8560081))
* **repairs:** add repair flow for deprecated API endpoint and missing configuration issues ([fe3f5f5](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/fe3f5f57213bcd0f138a073c49cc3e1cc5d920e7))
* resolve "latest" Home Assistant version via PyPI in devcontainer and bootstrap scripts ([cb2b7d7](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/cb2b7d7de94688112a2b602adb21f03e755124cf))
* **schema:** add JSON schema for icons.json and update file match settings ([ce5cc35](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/ce5cc3519d156ea5fbd571382ff43ec66de36cbd))
* **script:** enhance HA version sync validation ([29fb1ba](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/29fb1ba572c29d6c3af4212ecb86cb0a2ea7dd51))
* **script:** integrate dynamic detection of integration domain ([d859115](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/d859115b7d92cb64b0f779cc6b3228fce2364547)), closes [#69](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/issues/69)
* **scripts:** improve virtual environment activation logic with error handling ([163d729](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/163d7291d5928c3d31b3708900913c78d1e816b3))
* **scripts:** update virtual environment handling for improved compatibility across environments ([3ebd694](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/3ebd694649d25302287e0d965d67d2b36a2878c2))
* **setup:** enhance symlink creation for virtual environments and HACS integrations ([05abb6e](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/05abb6ea54948cc62c2d5404d48bd5ea220e9d25))
* show router host in reauth dialog ([de5773d](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/de5773d970d0ea5b5a3ac26270f50b2980d89f57))
* **tooling:** add Prettier and markdownlint-cli2 for Markdown linting ([ac71c4f](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/ac71c4fa581777124099325acf7175c8fb30ae8e))
* update documentation links and add examples for automations and dashboards ([fd28632](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/fd286327dcc11276b716ce318e8a511209ee4cf5))
* **workflows:** add pull_request trigger for copilot setup workflow ([1f1d499](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/1f1d499896a12db6383e5eb150b228fcdaf44f9e))
* **workflows:** refine cache restore keys for Home Assistant installation ([26a2cae](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/26a2caefde78ae8a7b76342a09f4af1dd9bd2b83))
* **workflows:** synchronize HA_VERSION across workflow files and enhance caching for dependencies ([0f7ed00](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/0f7ed008219a09eeaaca5876a7bf14d50400ec82))
* **workflows:** update cache actions for improved performance and reliability ([58a1678](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/58a16782b3d56c3304f2b4c4aee19e7a9037d0a2))


### Bug Fixes

* add HACS transition shim after domain rename ([de59c16](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/de59c1648c2b4f770d3864f7794badc73fa37789))
* **air_quality.py, diagnostic.py:** replace hardcoded units with constants for better maintainability ([3e9b52e](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/3e9b52ece5aba7e0720c088ea41d28f1475b1c35))
* **api:** auto-reconnect on session expiry after router reboot ([666f0ea](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/666f0ea5ea324e46a46fb31d2eb8815d49d474be))
* auto-merge pip patch/minor dependabot updates ([a26601f](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/a26601f14e20cfa17de2751320c112c35d988295))
* avoid dependabot auto-merge self-check deadlock ([0628a99](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/0628a996a6e4e04094562df3bb7f492ec4e1d02f))
* **ci:** resolve broken venv symlinks in GitHub Actions ([7469114](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/746911485e35c3c02746d1c9bbe55cef190dea5b))
* **config_flow:** use description placeholders for documentation URL ([17e4b0c](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/17e4b0c24acb00ffec16516a4dca706c70e0ae43))
* **config:** enable dual-stack IPv4/IPv6 and remote access ([8d918fb](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/8d918fb1bf5215ef6db44211fa87ee5a259aaa3a))
* **configuration.yaml:** change server_host to 0.0.0.0 for better accessibility ([4737431](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/47374315989ce877877f97393671686689f33033))
* **coordinator:** filter out unauthorized stations ([9514bdd](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/9514bdd0756ed56c878a05fd401dc8ad999f1593))
* create SSID presence sensors before clients connect ([bb19424](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/bb19424b323bb2643c9312fd9c1f9ad9d7d435c7))
* **devcontainer.json:** update container name for clarity ([e965fc5](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/e965fc56e21c94a906f28c350e8d76b4196609ff))
* **devcontainer:** fix EACCES race on container start by moving volume mounts ([8f78ea9](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/8f78ea92a17366e9b626815ce21989417689b4a0)), closes [#56](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/issues/56)
* **dev:** ensure clean restart by killing debugpy process ([d204f0b](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/d204f0b01056fb65c35df317f908c3eef2618e62))
* **device-tracker:** ensure compatibility with Home Assistant 2026.6.0 changes ([5f83c8d](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/5f83c8d8b5dce81cfc8a13e28de5cd81782786c3))
* **diagnostics.py:** improve security by redacting sensitive data in diagnostics ([f6cf9a8](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/f6cf9a8b53aea40f548f8f7c376e34c8be8d6d2d))
* **docs:** add release documentation and update release guidelines ([d759049](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/d7590494e2a94ac06cd435194328f83ee383c39f))
* **docs:** enhance test instructions with detailed examples and best practices for mocking and registry testing ([5530503](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/5530503cb189680ebc44f00019759faf13524e73))
* **docs:** update architecture documentation to reflect coordinator package structure and functionality ([dffd8e1](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/dffd8e1050e8bfecbe1478b3b5d37d4bb40a068b))
* **hacs.json:** update Home Assistant version to 2025.11.3 ([c39962b](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/c39962b8cf7d91debf93d3f599fe46fc16cb7300))
* handle ubus error code 2 in per-device wireless status calls ([db2ecb6](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/db2ecb621678656ac33b0703dfe729b580040bb7))
* include router host in entity_id to avoid duplicates with multiple routers ([373a731](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/373a73188dd2c62da9417910866a9c86a608d607))
* **initialize.sh:** remove unused README template exclusion and related dry-run messages ([81b8721](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/81b8721804d68f6d8c7d11d28dc0efcf115d0ad9))
* **init:** prevent false "uncommitted changes" warning in containers ([e5bcbbf](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/e5bcbbf426d1ecdcf60adf781df63ea17778df4a))
* make tag workflow idempotent when tag already exists ([bc87a45](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/bc87a4561b6bcd9fbe645f849cd7f073c2792483))
* **manifest.json:** add integration type ([9d5ed64](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/9d5ed64c444a484a2cda7be8db933bf281f1fab5))
* merge device_tracker entities across multiple routers via mac_address ([af7cd9e](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/af7cd9e4d5a45a624e27dc549a7e9f2a784a52fb))
* prevent duplicate device_tracker entities in multi-router setups ([8637a5b](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/8637a5b68e6091ecbe0e325aaf5364c5703703f7))
* probe wireless status capabilities for OpenWrt 25.x ([df5e3b6](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/df5e3b6c380542ab894a2285860ecbf30e6124e7))
* resolve lint issues in wifi presence integration ([0f9c01e](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/0f9c01e87bf7ddc9d2d03a2037de655e40430398))
* run dependabot auto-merge for dependabot PR author ([76ac6bd](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/76ac6bd62041bc45efec9a36844f6021f6c5f3e8))
* **schemas:** use inline YAML schema declarations ([2b7e1a1](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/2b7e1a1d7367067514e762911ec7dae594460d9a))
* **services:** improve service registration and add logging for missing config entries ([0c0bcb4](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/0c0bcb4e0e55bdc179d18dd7acc01bd95979e65f))
* **setup:** update symlink creation for external venv to use absolute path for reliability ([f4f8c30](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/f4f8c30a74b671d8daece9222d0585d840444abb))
* **translations:** replace plain URL with markdown link in config flow ([8bd713c](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/8bd713c70f156c886f438fa1d31174535ce09c8f))


### Performance

* **devcontainer:** move node_modules off workspace bind mount ([f32d778](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/f32d77800eaee64f4a683539d1853ecd187f088d))


### Code Refactoring

* remove legacy compatibility component path ([96ce247](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/96ce2471f32104f16c2aea9b7ed83c829d83ec55))

## [0.4.7](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/compare/v0.4.6...v0.4.7) (2026-07-24)


### Bug Fixes

* **docs:** add release documentation and update release guidelines ([d759049](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/d7590494e2a94ac06cd435194328f83ee383c39f))

## [0.4.6](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/compare/v0.4.5...v0.4.6) (2026-07-24)


### Bug Fixes

* **coordinator:** filter out unauthorized stations ([9514bdd](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/9514bdd0756ed56c878a05fd401dc8ad999f1593))

## [0.4.6](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/compare/v0.4.5...v0.4.6) (2026-07-24)

### Bug Fixes

- **coordinator:** filter out unauthorized stations in iwinfo and hostapd ([9514bdd](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/9514bdd))

## [0.4.5](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/compare/v0.4.4...v0.4.5) (2026-07-12)

### Bug Fixes

- **device-tracker:** ensure compatibility with Home Assistant 2026.6.0 changes ([5f83c8d](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/5f83c8d8b5dce81cfc8a13e28de5cd81782786c3))

## [0.4.4](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/compare/v0.4.3...v0.4.4) (2026-07-12)

### Features

- **devcontainer:** add version sync script and workflow ([bb4e499](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/bb4e499311b73b4efdeac8b578a69fd5138b7355))
- **script:** enhance HA version sync validation ([29fb1ba](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/29fb1ba572c29d6c3af4212ecb86cb0a2ea7dd51))
- **script:** integrate dynamic detection of integration domain ([d859115](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/d859115b7d92cb64b0f779cc6b3228fce2364547)), closes [#69](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/issues/69)

## [0.4.3](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/compare/v0.4.2...v0.4.3) (2026-05-02)

### Bug Fixes

- create SSID presence sensors before clients connect ([bb19424](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/bb19424b323bb2643c9312fd9c1f9ad9d7d435c7))

## [0.4.2](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/compare/v0.4.1...v0.4.2) (2026-05-02)

### Features

- add SSID presence binary sensor platform ([f20dfaa](https://github.com/zewelor/homeassistant-openwrt-ubus-wifi-presence/commit/f20dfaa4caad6e43eff3f9c06bba3a8d4773b5f9))
