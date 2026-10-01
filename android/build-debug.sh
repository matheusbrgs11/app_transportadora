#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ -d ../.local/toolchains/jdk-17.0.20.1+1 ]]; then
  source ../scripts/android-env.sh
fi
command -v java >/dev/null || { echo 'Falta JDK 17. Android Studio não é necessário.' >&2; exit 1; }
if [[ -z "${ANDROID_HOME:-}" && ! -f local.properties ]]; then
  echo 'Configure ANDROID_HOME para o SDK Android (plataforma 35 e build-tools 35.0.0).' >&2
  exit 1
fi
exec ./gradlew --no-daemon :app:assembleDebug :app:lintDebug
