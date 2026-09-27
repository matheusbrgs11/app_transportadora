#!/usr/bin/env bash
set -euo pipefail
coleta_package_root="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -d "$coleta_package_root/.local/toolchains/jdk-17.0.20.1+1" ]]; then
  source "$coleta_package_root/scripts/android-env.sh"
fi
gradle -p "$coleta_package_root/android" --no-daemon --max-workers=2 :app:assembleStaging :app:lintStaging
coleta_package_dir="$coleta_package_root/.local/homologacao"
mkdir -p "$coleta_package_dir"
cp "$coleta_package_root/android/app/build/outputs/apk/staging/app-staging.apk" "$coleta_package_dir/coleta-homologacao.apk"
python3 - "$coleta_package_root" <<'PY'
from pathlib import Path
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
root=Path(sys.argv[1]);folder=root/'.local/homologacao';apk=folder/'coleta-homologacao.apk'
info={'gerado_em':datetime.now(timezone.utc).isoformat(),
      'commit_base':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
      'alteracoes_locais':bool(subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip()),
      'apk':apk.name,'sha256':hashlib.sha256(apk.read_bytes()).hexdigest(),
      'application_id':'br.com.coleta.motorista.homologacao',
      'assinatura':'chave debug local; somente homologacao','https_obrigatorio':True}
(folder/'build.json').write_text(json.dumps(info,indent=2)+'\n')
print('APK e identificação:',folder)
PY
