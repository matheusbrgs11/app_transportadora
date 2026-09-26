#!/usr/bin/env bash
set -euo pipefail
coleta_test_root="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -d "$coleta_test_root/.local/toolchains/jdk-17.0.20.1+1" ]]; then
  source "$coleta_test_root/scripts/android-env.sh"
fi
exec gradle -p "$coleta_test_root/android" --no-daemon --max-workers=2 :app:testDebugUnitTest :app:assembleDebug :app:lintDebug
