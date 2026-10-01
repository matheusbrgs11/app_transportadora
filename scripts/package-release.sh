#!/usr/bin/env bash
set -euo pipefail
coleta_release_root="$(cd "$(dirname "$0")/.." && pwd)"
for required in COLETA_KEYSTORE_FILE COLETA_KEYSTORE_PASSWORD COLETA_KEY_ALIAS COLETA_KEY_PASSWORD; do
  if [[ -z "${!required:-}" ]]; then
    echo "Configure $required fora do repositório antes de gerar a versão comercial." >&2
    exit 2
  fi
done
if [[ ! -f "$COLETA_KEYSTORE_FILE" ]]; then echo 'Arquivo de assinatura não encontrado.' >&2; exit 2; fi
if [[ -d "$coleta_release_root/.local/toolchains/jdk-17.0.20.1+1" ]]; then
  source "$coleta_release_root/scripts/android-env.sh"
fi
"$coleta_release_root/android/gradlew" -p "$coleta_release_root/android" --no-daemon --max-workers=2 :app:testReleaseUnitTest :app:assembleRelease :app:lintRelease
coleta_apk="$coleta_release_root/android/app/build/outputs/apk/release/app-release.apk"
coleta_signer="${ANDROID_HOME:?Configure ANDROID_HOME}/build-tools/35.0.0/apksigner"
"$coleta_signer" verify --verbose "$coleta_apk" >/dev/null
coleta_output="$coleta_release_root/.local/release"
mkdir -p "$coleta_output"
cp "$coleta_apk" "$coleta_output/coleta-motorista-release.apk"
python3 - "$coleta_release_root" <<'PY'
from pathlib import Path
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
root=Path(sys.argv[1]);folder=root/'.local/release';apk=folder/'coleta-motorista-release.apk'
info={'gerado_em':datetime.now(timezone.utc).isoformat(),
      'commit_base':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
      'alteracoes_locais':bool(subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip()),
      'apk':apk.name,'sha256':hashlib.sha256(apk.read_bytes()).hexdigest(),
      'application_id':'br.com.coleta.motorista','https_obrigatorio':True}
(folder/'build.json').write_text(json.dumps(info,indent=2)+'\n')
print('APK comercial assinado e manifesto:',folder)
PY
