# GitHub Codespaces Development Guide

This repository includes a DevContainer configuration suitable for GitHub Codespaces.

## Quick Start

1. Open the repository on GitHub.
2. Select **Code -> Codespaces -> Create codespace on main**.
3. Wait for the DevContainer setup to finish.
4. Run the validation suite:

   ```bash
   ./script/check
   ./script/test
   ```

5. Start Home Assistant when runtime testing is needed:

   ```bash
   ./script/develop
   ```

Home Assistant listens on port 8123, which Codespaces should offer to forward in the
**Ports** panel.

## Testing a Pull Request

1. Open the pull request on GitHub.
2. Select **Code -> Create codespace on `<branch-name>`**.
3. Run `./script/check` and `./script/test`.
4. Run `./script/develop` for manual Home Assistant testing.
5. Open the forwarded port 8123 URL.

For the Copilot Coding Agent workflow, see [COPILOT_AGENT.md](COPILOT_AGENT.md).

## What the DevContainer Provides

- Python and the Home Assistant development environment
- project development and validation scripts
- recommended VS Code extensions
- automatic port forwarding support for Home Assistant
- host GitHub authentication where supported by the Codespaces environment
- restoration of `node_modules` when its Docker volume is empty

## Differences from Local Development

### Port Access

- **Codespaces:** use the forwarded URL shown in the **Ports** panel.
- **Local DevContainer:** use `http://localhost:8123` unless the container tooling
  exposes a different address.

### Git Configuration

- **Codespaces:** GitHub authentication is normally provided by the environment.
- **Local:** Git uses the host configuration mounted into the DevContainer.

### Persistence

Workspace files and Git changes persist when a Codespace is stopped. Development
volumes may be recreated or pruned, so the post-attach hook restores JavaScript
dependencies when necessary.

## Troubleshooting

### Many editor problems after the first build

Python extensions can start indexing before dependency setup finishes.

1. Wait for setup commands to complete.
2. Open the command palette with `F1`.
3. Run **Developer: Reload Window**.

### Port 8123 is not forwarded

1. Confirm `./script/develop` is running.
2. Open the **Ports** panel.
3. Add port `8123` manually when it is not detected.

### Git push authentication fails

Check that the Codespace has access to the repository and reauthenticate through the
GitHub integration offered by the environment.

## Resources

- [GitHub Codespaces documentation](https://docs.github.com/en/codespaces)
- [GitHub Codespaces billing](https://docs.github.com/en/billing/managing-billing-for-github-codespaces)
