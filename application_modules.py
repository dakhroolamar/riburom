"""Application composition root for RI BUROM feature modules.

Keep module registration in one place so Gunicorn/WSGI and direct local execution
assemble the same Flask application.
"""


def register_application_modules(flask_app):
    if getattr(flask_app, '_ri_burom_feature_modules_registered', False):
        return
    flask_app._ri_burom_feature_modules_registered = True

    from cms_routes import (
        register_workspace,
        marketplace_view_required,
        marketplace_manage_required,
        marketplace_inquiry_view_required,
        marketplace_inquiry_manage_required,
    )
    from cms_typography import register_typography
    from cms_backgrounds import register_section_backgrounds
    from marketplace_admin import register_marketplace_admin
    from marketplace_service_media import register_marketplace_service_media
    from marketplace_inquiries import register_marketplace_inquiries
    from marketplace_inquiry_admin import register_marketplace_inquiry_admin
    from marketplace_appearance import register_marketplace_appearance
    from notifications import register_notifications
    from seo import register_seo
    from hero_animation_routes import register_hero_animation_routes

    register_workspace(flask_app)
    register_typography(flask_app)
    register_section_backgrounds(flask_app)
    register_marketplace_admin(
        flask_app,
        marketplace_view_required,
        marketplace_manage_required,
    )
    register_marketplace_service_media(flask_app, marketplace_manage_required)
    register_marketplace_inquiries(flask_app)
    register_marketplace_inquiry_admin(
        flask_app,
        marketplace_inquiry_view_required,
        marketplace_inquiry_manage_required,
    )
    register_marketplace_appearance(flask_app)
    register_notifications(flask_app)
    register_seo(flask_app)
    register_hero_animation_routes(flask_app)
