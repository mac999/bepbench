"""WSGI entry point used by gunicorn in the container."""

from bepkit.app import create_app

app = create_app()
