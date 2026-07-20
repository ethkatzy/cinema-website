import os
import secrets
from pathlib import Path

_SECRET_KEY_FILE = Path(__file__).parent / ".secret_key"


def _load_secret_key():
    env_key = os.environ.get("CINEMA_SECRET_KEY")
    if env_key:
        return env_key
    if _SECRET_KEY_FILE.exists():
        return _SECRET_KEY_FILE.read_text().strip()
    key = secrets.token_hex(32)
    _SECRET_KEY_FILE.write_text(key)
    return key


secret_key = _load_secret_key()
