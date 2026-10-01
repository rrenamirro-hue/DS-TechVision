"""Crea credenciales aleatorias fuera del repositorio; imprime la clave solo una vez."""
import argparse
import base64
import json
import secrets
from pathlib import Path

from .auth import default_config_path, password_hash


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=default_config_path())
    parser.add_argument('--username', default='tecnico')
    args = parser.parse_args()
    if args.output.exists():
        print(f'AUTH_CONFIG_EXISTS={args.output}')
        return
    password = secrets.token_urlsafe(15)
    salt = secrets.token_bytes(16)
    config = {'username': args.username,
              'salt': base64.urlsafe_b64encode(salt).decode('ascii'),
              'password_hash': base64.urlsafe_b64encode(password_hash(password, salt)).decode('ascii'),
              'session_secret': base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('ascii').rstrip('=')}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(config, indent=2), encoding='utf-8')
    print(f'AUTH_CONFIG_CREATED={args.output}')
    print(f'USERNAME={args.username}')
    print(f'INITIAL_PASSWORD={password}')
    print('Guarda la clave ahora: no se vuelve a mostrar.')


if __name__ == '__main__':
    main()
