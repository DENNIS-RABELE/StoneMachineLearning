#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path


def _load_dotenv():
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _apply_default_runserver_port():
    port = os.getenv("PORT")
    if not port or "runserver" not in sys.argv:
        return
    idx = sys.argv.index("runserver")
    if len(sys.argv) > idx + 1 and not sys.argv[idx + 1].startswith("-"):
        return
    sys.argv.insert(idx + 1, f"127.0.0.1:{port}")


def main():
    """Run administrative tasks."""
    _load_dotenv()
    _apply_default_runserver_port()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bettor_service.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
