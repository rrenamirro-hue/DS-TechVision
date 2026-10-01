"""Autenticacion local sin secretos dentro del repositorio."""
import base64
import hashlib
import hmac
import json
import os
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import Response

COOKIE_NAME = 'ds_session'
SESSION_SECONDS = 8 * 60 * 60


class AuthenticationError(Exception):
    pass


def default_config_path() -> Path:
    base = Path(os.environ.get('LOCALAPPDATA') or (Path.home() / '.ds_techvision'))
    return base / 'DataSystems' / 'DS_TechVision' / 'auth.json'


def config_path() -> Path:
    custom = os.environ.get('DS_TECHVISION_AUTH_CONFIG')
    return Path(custom).expanduser().resolve() if custom else default_config_path()


def _read_config() -> dict:
    path = config_path()
    if not path.is_file():
        raise AuthenticationError(f'Configuracion de acceso ausente: {path}')
    try:
        config = json.loads(path.read_text(encoding='utf-8'))
        if not {'username', 'salt', 'password_hash', 'session_secret'}.issubset(config):
            raise ValueError('faltan campos')
        return config
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise AuthenticationError('Configuracion de acceso invalida') from exc


def require_auth_config() -> None:
    _read_config()


def password_hash(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode('utf-8'), salt=salt, n=2**14, r=8, p=1, dklen=32)


def verify_credentials(username: str, password: str) -> bool:
    try:
        config = _read_config()
        username_ok = hmac.compare_digest(username, config['username'])
        actual = password_hash(password, base64.urlsafe_b64decode(config['salt']))
        password_ok = hmac.compare_digest(actual, base64.urlsafe_b64decode(config['password_hash']))
        return username_ok and password_ok
    except (AuthenticationError, ValueError, KeyError):
        return False


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('ascii').rstrip('=')


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + '=' * (-len(data) % 4))


def create_session(username: str) -> str:
    config = _read_config()
    payload = json.dumps({'sub': username, 'iat': int(time.time()), 'exp': int(time.time()) + SESSION_SECONDS},
                         separators=(',', ':')).encode('utf-8')
    encoded = _b64(payload)
    signature = hmac.new(_unb64(config['session_secret']), encoded.encode('ascii'), hashlib.sha256).digest()
    return f'{encoded}.{_b64(signature)}'


def verify_session(token: str | None) -> str:
    if not token or '.' not in token:
        raise AuthenticationError('Sesion ausente')
    try:
        encoded, supplied = token.split('.', 1)
        config = _read_config()
        expected = hmac.new(_unb64(config['session_secret']), encoded.encode('ascii'), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _unb64(supplied)):
            raise AuthenticationError('Sesion invalida')
        payload = json.loads(_unb64(encoded))
        if int(payload['exp']) < int(time.time()) or payload['sub'] != config['username']:
            raise AuthenticationError('Sesion vencida')
        return str(payload['sub'])
    except (ValueError, KeyError, json.JSONDecodeError, AuthenticationError) as exc:
        if isinstance(exc, AuthenticationError):
            raise
        raise AuthenticationError('Sesion invalida') from exc


def set_session_cookie(response: Response, token: str, secure: bool) -> None:
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_SECONDS, httponly=True,
                        secure=secure, samesite='lax', path='/')


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path='/', httponly=True, samesite='lax')


class LoginThrottle:
    """Limite simple por proceso: cinco fallos por IP en sesenta segundos."""
    def __init__(self):
        self.failures = defaultdict(deque)

    def _recent(self, key: str):
        now = time.monotonic()
        queue = self.failures[key]
        while queue and now - queue[0] > 60:
            queue.popleft()
        return queue

    def allowed(self, key: str) -> bool:
        return len(self._recent(key)) < 5

    def failed(self, key: str) -> None:
        self._recent(key).append(time.monotonic())

    def succeeded(self, key: str) -> None:
        self.failures.pop(key, None)
