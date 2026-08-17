"""Production WSGI entrypoint with the separated RI BUROM workspace layer."""

from flask import redirect, url_for

from app import app
from cms_routes import register_workspace, marketplace_view_required, marketplace_manage_required
from cms_typography import register_typography
from cms_backgrounds import register_section_backgrounds
from marketplace_admin import register_marketplace_admin
from notifications import register_notifications
from seo import register_seo

register_workspace(app)
register_typography(app)
register_section_backgrounds(app)
register_marketplace_admin(app, marketplace_view_required, marketplace_manage_required)
register_notifications(app)
register_seo(app)


# Compatibility guard: keep the legacy /admin URL from opening the old,
# crowded Control Room after the workspace migration. The existing endpoint
# name is preserved because older POST handlers still redirect to /admin.
def _legacy_admin_redirect():
    return redirect(url_for('workspace_operations'))


app.view_functions['admin'] = _legacy_admin_redirect
