"""Production WSGI entrypoint with the separated RI BUROM workspace layer."""

from app import app
from cms_routes import register_workspace
from cms_typography import register_typography
from cms_backgrounds import register_section_backgrounds

register_workspace(app)
register_typography(app)
register_section_backgrounds(app)
