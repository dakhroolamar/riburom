"""Production WSGI entrypoint with the separated RI BUROM workspace layer."""

from app import app
from cms_routes import register_workspace

register_workspace(app)
