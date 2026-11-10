#!/bin/bash
# Compatibility entry point; all processing runs natively on the Mac.
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
exec bash "$SCRIPT_DIR/patcher.sh" "$@"
