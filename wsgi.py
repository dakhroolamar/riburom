"""Production WSGI entrypoint with the separated RI BUROM workspace layer."""

from app import app
from cms_routes import register_workspace
from cms_typography import register_typography

register_workspace(app)
register_typography(app)
