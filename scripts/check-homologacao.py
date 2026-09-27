#!/usr/bin/env python3
"""Read-only HTTPS checks; no credentials, GPS or changes to the database."""
import argparse
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url', help='Panel origin, for example https://test.example.com')
    args = parser.parse_args()
    parsed = urlsplit(args.url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
        parser.error('Informe somente a origem HTTPS do painel, sem credenciais, caminho ou parâmetros.')
    origin = args.url.rstrip('/')
    opener = build_opener(NoRedirect())
    checks = [('/', 200, 'text/html'), ('/api/rastreamento', 401, 'application/json')]
    failed = False
    for path, expected, content_type in checks:
        try:
            try:
                response = opener.open(Request(origin+path, headers={'Accept': content_type}), timeout=15)
            except HTTPError as exc:
                response = exc
            with response:
                body = response.read(65536)
                ok = response.status == expected and content_type in response.headers.get('Content-Type', '')
                if expected == 401:
                    try:
                        ok = ok and isinstance(json.loads(body).get('detail'), str)
                    except (ValueError, AttributeError):
                        ok = False
                print(f'{path}: HTTP {response.status} — '+('OK' if ok else 'FALHOU'))
                failed |= not ok
        except (URLError, TimeoutError, OSError):
            print(f'{path}: falha de conexão/TLS; confira DNS, certificado e serviço.')
            failed = True
    if not failed:
        print('HTTPS e proteção básica conferidos. Login, banco, isolamento e Android ainda exigem teste autenticado.')
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
