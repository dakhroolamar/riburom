"""Production WSGI entrypoint for RI BUROM."""

from app import app
from application_modules import register_application_modules

register_application_modules(app)
