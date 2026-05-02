#!/bin/bash
# download.sh: Resilient file download helper for setup and validation scripts.
#
# Provides _download() which wraps curl with retry and timeout handling.

_download() {
    local url="$1" dest="$2" attempt max_attempts delay
    max_attempts=3
    delay=2
    for ((attempt = 1; attempt <= max_attempts; attempt++)); do
        if curl -fsSL \
            --connect-timeout 10 \
            --max-time 60 \
            --retry 0 \
            "$url" -o "$dest"; then
            return 0
        fi
        if ((attempt < max_attempts)); then
            log_warning "Download failed (attempt ${attempt}/${max_attempts}): ${url##*/} - retrying in ${delay}s..."
            sleep "$delay"
            delay=$((delay * 2))
        fi
    done
    log_error "Download failed after ${max_attempts} attempts: $url"
    return 1
}
