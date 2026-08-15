"""Per-section public background image controls for the RI BUROM CMS."""

from functools import wraps
import json

from flask import abort, flash, redirect, render_template, request, url_for

from app import app, add_audit, get_current_user, get_public_config, get_site_settings, _with_defaults if False else None
