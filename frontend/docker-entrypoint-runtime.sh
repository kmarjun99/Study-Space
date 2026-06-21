#!/bin/sh
set -eu

api_base_url="${BACKEND_URL:-${VITE_API_BASE_URL:-}}"

# Escape the small subset needed for a JavaScript string literal. Backend URLs
# are expected to be normal http(s) URLs, but escaping keeps generation safe.
escaped_api_base_url="$(
  printf '%s' "$api_base_url" |
    sed 's/\\/\\\\/g; s/"/\\"/g'
)"

printf 'window.__MYSPACE_RUNTIME_CONFIG__ = { API_BASE_URL: "%s" };\n' \
  "$escaped_api_base_url" \
  > /usr/share/nginx/html/env-config.js

envsubst '$PORT' \
  < /etc/nginx/templates/default.conf.template \
  > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'
