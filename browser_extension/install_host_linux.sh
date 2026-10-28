#!/usr/bin/env bash
set -euo pipefail

extension_id="${1:-icdicciedmiojchchcagghmpkbenkccj}"
if [[ ! "$extension_id" =~ ^[a-p]{32}$ ]]; then
  echo "Usage: $0 <32-character Chrome/Edge extension ID>" >&2
  exit 2
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
host_path="$script_dir/aegis_host_linux.sh"
if [[ ! -x "$host_path" ]]; then
  echo "Native host launcher is not executable: $host_path" >&2
  echo "Run: chmod +x '$host_path'" >&2
  exit 1
fi

install_manifest() {
  local browser_dir="$1"
  local scheme="$2"
  mkdir -p "$browser_dir"
  python3 - "$browser_dir/com.aegis.downloadmanager.json" "$host_path" "$scheme" "$extension_id" <<'PY'
import json
import os
import sys

manifest_path, host_path, scheme, extension_id = sys.argv[1:]
manifest = {
    "name": "com.aegis.downloadmanager",
    "description": "Aegis Download Manager Native Messaging Host",
    "path": os.path.realpath(host_path),
    "type": "stdio",
    "allowed_origins": [f"{scheme}://{extension_id}/"],
}
with open(manifest_path, "w", encoding="utf-8") as output:
    json.dump(manifest, output, indent=2)
    output.write("\n")
PY
  printf 'Registered native host: %s\n' "$browser_dir/com.aegis.downloadmanager.json"
}

install_manifest "$HOME/.config/google-chrome/NativeMessagingHosts" "chrome-extension"
install_manifest "$HOME/.config/chromium/NativeMessagingHosts" "chrome-extension"
install_manifest "$HOME/.config/BraveSoftware/Brave-Browser/NativeMessagingHosts" "chrome-extension"
install_manifest "$HOME/.config/microsoft-edge/NativeMessagingHosts" "edge-extension"

printf '\nLoad the browser_extension folder as an unpacked extension, then pass its ID to this script if it differs from the supplied ID.\n'
