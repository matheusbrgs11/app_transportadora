#!/usr/bin/env bash
set -euo pipefail
coleta_verify_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$coleta_verify_root"
"$coleta_verify_root/.venv/bin/python" -m pytest -q
npm --prefix "$coleta_verify_root/frontend" run build
"$coleta_verify_root/scripts/test-android.sh"
echo 'Backend, painel e Android aprovados. Testes físicos e nuvem continuam separados.'
