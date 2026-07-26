#!/usr/bin/env bash
#
# .devcontainer/post-attach.sh - DevContainer Post-Attach Hook
#
# Restores development dependencies when needed and runs project-specific hooks.

set -euo pipefail

YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

print_color() {
    local color=$1
    shift
    echo -e "${color}$*${NC}" >&2
}

print_info() {
    print_color "$CYAN" "ℹ $1"
}

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Load DevContainer environment overrides (.env -> .env.local, later wins).
# shellcheck source=.devcontainer/_load_env.sh
source "$SCRIPT_DIR/_load_env.sh"

# Run project pre-hook if present.
_hook_file="$SCRIPT_DIR/hooks/post-attach.pre.sh"
if [[ -f "$_hook_file" ]]; then
    print_info "Running hook: .devcontainer/hooks/post-attach.pre.sh"
    # shellcheck source=/dev/null
    source "$_hook_file"
fi
unset _hook_file

# Hide the default Codespaces first-run notice so project MOTD stays primary.
mkdir -p "$HOME/.config/vscode-dev-containers"
touch "$HOME/.config/vscode-dev-containers/first-run-notice-already-displayed"

# The named Docker volume may be pruned while the container is stopped.
# postCreateCommand only runs on container creation, so restore node_modules on attach.
if command -v npm >/dev/null 2>&1 && [[ -f package.json ]] && [[ -z "$(ls -A node_modules 2>/dev/null)" ]]; then
    print_color "$YELLOW" "⚠ node_modules is empty — running npm ci to restore packages..."
    npm ci --silent
fi

# Run project post-hook if present.
_hook_file="$SCRIPT_DIR/hooks/post-attach.post.sh"
if [[ -f "$_hook_file" ]]; then
    print_info "Running hook: .devcontainer/hooks/post-attach.post.sh"
    # shellcheck source=/dev/null
    source "$_hook_file"
fi
unset _hook_file
