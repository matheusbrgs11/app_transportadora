#!/usr/bin/env bash
set -euo pipefail
coleta_usb_root="$(cd "$(dirname "$0")/.." && pwd)"
source "$coleta_usb_root/scripts/android-env.sh"
# An explicit serial is required if multiple authorized devices are connected.
coleta_usb_serial="${1:-}"
if [[ -z "$coleta_usb_serial" ]]; then
  mapfile -t coleta_usb_devices < <(adb devices | awk 'NR>1 && $2=="device" {print $1}')
  if [[ "${#coleta_usb_devices[@]}" != 1 ]]; then
    echo "Conecte e autorize um único Android USB, ou informe o serial como argumento."
    adb devices -l
    exit 1
  fi
  coleta_usb_serial="${coleta_usb_devices[0]}"
fi
[[ "$(adb -s "$coleta_usb_serial" get-state)" == device ]]
coleta_usb_sdk="$(adb -s "$coleta_usb_serial" shell getprop ro.build.version.sdk | tr -d '\r')"
if ! [[ "$coleta_usb_sdk" =~ ^[0-9]+$ ]] || (( coleta_usb_sdk < 26 )); then
  echo "Requer Android 8 ou mais recente."; exit 1
fi
"$coleta_usb_root/.venv/bin/python" - <<'PY'
import httpx
r=httpx.get('http://127.0.0.1:8000/health',timeout=5,trust_env=False)
r.raise_for_status()
print('API local disponível.')
PY
"$coleta_usb_root/android/gradlew" -p "$coleta_usb_root/android" --no-daemon --max-workers=2 :app:assembleUsb :app:lintUsb
adb -s "$coleta_usb_serial" reverse tcp:8000 tcp:8000
# No uninstall, data clearing, automatic permission grants or downgrades.
adb -s "$coleta_usb_serial" install -r "$coleta_usb_root/android/app/build/outputs/apk/usb/app-usb.apk"
adb -s "$coleta_usb_serial" shell am start -n br.com.coleta.motorista.homologacao.usb/br.com.coleta.motorista.MainActivity
echo "Instalado: Coleta Teste USB. Servidor: http://127.0.0.1:8000"
echo "Mantenha cabo e servidor conectados; após desconectar/refazer ADB, repita o encaminhamento."
