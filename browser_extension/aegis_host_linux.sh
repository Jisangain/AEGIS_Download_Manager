#!/usr/bin/env bash
set -euo pipefail

host_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$host_dir/aegis_host.py"
