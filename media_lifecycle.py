"""Marketplace media reference checks and safe cleanup."""

from marketplace_models import Provider, Service, ServiceImage
from storage import delete_media


def marketplace_media_is_referenced(value):
    if not value:
        return False
    return bool(
        Provider.query.filter_by(image_url=value).first()
        or Service.query.filter_by(image_url=value).first()
        or ServiceImage.query.filter_by(image_url=value).first()
    )


def delete_marketplace_media_if_unreferenced(value):
    """Delete media only after all marketplace database references are gone."""
    if not value or marketplace_media_is_referenced(value):
        return False
    delete_media(value)
    return True
