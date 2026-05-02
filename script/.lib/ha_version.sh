#!/bin/bash
# ha_version.sh: Home Assistant version resolution for setup and validation scripts.

_PYPI_JSON_CACHE=""

_pypi_populate_cache() {
    [[ -n "$_PYPI_JSON_CACHE" ]] && return 0

    local attempt max_attempts delay output
    max_attempts=3
    delay=2

    for ((attempt = 1; attempt <= max_attempts; attempt++)); do
        if output=$(curl -fsSL \
            --connect-timeout 10 \
            --max-time 30 \
            https://pypi.org/pypi/homeassistant/json); then
            _PYPI_JSON_CACHE="$output"
            return 0
        fi
        if ((attempt < max_attempts)); then
            log_warning "PyPI request failed (attempt ${attempt}/${max_attempts}), retrying in ${delay}s..."
            sleep "$delay"
            delay=$((delay * 2))
        fi
    done

    log_error "Failed to reach PyPI after ${max_attempts} attempts"
    return 1
}

_PYPI_SORT_KEY_PY='
import sys, re
def key(v):
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)((?:a|b|rc)\d+)?$", v)
    if not m:
        return (0, 0, 0, 3, 0)
    year, month, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
    pre = m.group(4) or ""
    pm = re.match(r"^(a|b|rc)(\d+)$", pre) if pre else None
    prank = {"a": 0, "b": 1, "rc": 2}.get(pm.group(1), 3) if pm else 3
    pnum  = int(pm.group(2)) if pm else 0
    return (year, month, patch, prank, pnum)
versions = [v.strip() for v in sys.stdin]
print(sorted(versions, key=key)[-1] if versions else "")
'

resolve_ha_version() {
    local -n _rha_result="$1"
    local version="$2"
    local resolved

    if [[ "$version" == "latest" ]]; then
        log_info "Resolving latest Home Assistant version via PyPI..."
        _pypi_populate_cache || return 1
        resolved=$(printf '%s' "$_PYPI_JSON_CACHE" |
            python3 -c 'import sys, json; print(json.load(sys.stdin)["info"]["version"])')
        if [[ -z "$resolved" ]]; then
            log_error "Failed to resolve latest Home Assistant version from PyPI"
            return 1
        fi
        log_info "Resolved to: ${resolved}"
        _rha_result="$resolved"
        return 0
    fi

    if [[ "$version" == "beta" ]]; then
        log_info "Resolving latest Home Assistant pre-release version via PyPI..."
        _pypi_populate_cache || return 1
        resolved=$(printf '%s' "$_PYPI_JSON_CACHE" |
            python3 -c 'import sys, json, re
data = json.load(sys.stdin)
pre = [v for v in data["releases"] if re.match(r"^\d{4}\.\d+\.\d+(a|b|rc)\d+$", v)]
sys.stdout.write("\n".join(pre))
' | python3 -c "$_PYPI_SORT_KEY_PY")
        if [[ -z "$resolved" ]]; then
            log_error "Failed to resolve latest Home Assistant pre-release version from PyPI"
            return 1
        fi
        log_info "Resolved to: ${resolved}"
        _rha_result="$resolved"
        return 0
    fi

    if [[ "$version" =~ ^[0-9]{4}\.[0-9]+$ ]]; then
        local minor_prefix
        minor_prefix="${version}."
        log_info "Resolving latest patch for Home Assistant ${minor_prefix%.} via PyPI..."
        _pypi_populate_cache || return 1
        resolved=$(printf '%s' "$_PYPI_JSON_CACHE" |
            python3 -c 'import sys, json
prefix = sys.argv[1]
data = json.load(sys.stdin)
versions = sorted(
    [v for v in data["releases"] if v.startswith(prefix) and all(p.isdigit() for p in v.split("."))],
    key=lambda v: int(v.split(".")[-1])
)
print(versions[-1] if versions else "")
' "$minor_prefix")
        if [[ -z "$resolved" ]]; then
            log_error "Failed to resolve latest patch for Home Assistant ${minor_prefix%.} from PyPI"
            return 1
        fi
        log_info "Resolved to: ${resolved}"
        _rha_result="$resolved"
        return 0
    fi

    _rha_result="$version"
}
