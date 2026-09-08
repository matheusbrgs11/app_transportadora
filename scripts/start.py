"""Inicia o painel e a API juntos. Ctrl+C encerra ambos, preservando o banco."""
from pathlib import Path
import os
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]


def main():
    if not (ROOT/'frontend/node_modules/.bin/vite').exists():
        raise SystemExit('Instale o painel primeiro: npm --prefix frontend ci')
    processes=[]
    try:
        processes.append(subprocess.Popen([sys.executable,str(ROOT/'scripts/dev.py')],cwd=ROOT,start_new_session=True))
        processes.append(subprocess.Popen(['npm','run','dev'],cwd=ROOT/'frontend',start_new_session=True))
        print('Painel: http://127.0.0.1:5173/ — mantenha este terminal aberto.',flush=True)
        print('Se as portas já estiverem em uso, encerre a execução anterior antes de iniciar novamente.',flush=True)
        while all(p.poll() is None for p in processes):
            time.sleep(.5)
        failed=next((p.returncode for p in processes if p.poll() is not None and p.returncode),0)
        if failed:
            raise SystemExit(f'Um dos serviços encerrou com erro ({failed}). Confira a mensagem acima.')
    except KeyboardInterrupt:
        pass
    finally:
        for p in processes:
            try:
                os.killpg(p.pid,signal.SIGTERM)
            except ProcessLookupError:
                pass
        for p in processes:
            try:
                p.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid,signal.SIGKILL)
                p.wait()


if __name__=='__main__':
    main()
