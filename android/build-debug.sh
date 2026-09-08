#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
command -v java >/dev/null || { echo 'Falta JDK 17. Android Studio não é necessário.' >&2; exit 1; }
command -v gradle >/dev/null || { echo 'Falta Gradle 8.11.1 no PATH.' >&2; exit 1; }
if [[ -z "${ANDROID_HOME:-}" && ! -f local.properties ]]; then
  echo 'Configure ANDROID_HOME para o SDK Android (plataforma 35 e build-tools 35.0.0).' >&2
  exit 1
fi
exec gradle --no-daemon :app:assembleDebug :app:lintDebug
