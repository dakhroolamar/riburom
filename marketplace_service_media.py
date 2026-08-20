"""Service gallery management routes and workspace UI injection."""

from flask import abort, flash, redirect, render_template, request, url_for

from app import add_audit, get_current_user
from marketplace_models import Service, ServiceImage
from models import db
from storage import delete_media, save_image


def register_marketplace_service_media(flask_app, manage_required):
    if getattr(flask_app, '_ri_burom_marketplace_service_media_registered', False):
        return

    flask_app._ri_burom_marketplace_service_media_registered = True

    @flask_app.route('/workspace/marketplace/services/<int:id>/images', methods=['POST'])
    @manage_required
    def marketplace_service_images_upload(id):
        service = db.session.get(Service, id)
        if service is None:
            abort(404)

        files = [file for file in request.files.getlist('images') if file and file.filename]
        if not files:
            flash('Please select at least one service image.', 'error')
            return redirect(url_for('workspace_marketplace'))

        next_sort = max((image.sort_order for image in service.images), default=-1) + 1
        saved = []
        try:
            for file_storage in files:
                image_url = save_image(file_storage)
                saved.append(image_url)
                service.images.append(ServiceImage(
                    image_url=image_url,
                    alt_text=f'{service.name} image {next_sort + 1}',
                    sort_order=next_sort,
                ))
                next_sort += 1
        except ValueError as exc:
            for image_url in saved:
                delete_media(image_url)
            db.session.rollback()
            flash(str(exc), 'error')
            return redirect(url_for('workspace_marketplace'))

        if not service.image_url and service.images:
            service.image_url = service.images[0].image_url

        add_audit('uploaded', 'service_images', service.id, f'{service.name}; count={len(saved)}')
        db.session.commit()
        flash(f'{len(saved)} image(s) added to "{service.name}".', 'success')
        return redirect(url_for('workspace_marketplace'))

    @flask_app.route('/workspace/marketplace/services/<int:id>/images/<int:image_id>/delete', methods=['POST'])
    @manage_required
    def marketplace_service_image_delete(id, image_id):
        service = db.session.get(Service, id)
        image = db.session.get(ServiceImage, image_id)
        if service is None or image is None or image.service_id != service.id:
            abort(404)

        image_url = image.image_url
        was_primary = service.image_url == image_url
        db.session.delete(image)
        db.session.flush()

        if was_primary:
            replacement = service.images[0] if service.images else None
            service.image_url = replacement.image_url if replacement else None

        add_audit('deleted', 'service_image', image.id, f'{service.name}: {image_url}')
        db.session.commit()
        delete_media(image_url)

        flash('Service image removed.', 'success')
        return redirect(url_for('workspace_marketplace'))

    @flask_app.after_request
    def inject_service_gallery_manager(response):
        if request.path != '/workspace/marketplace' or response.status_code != 200:
            return response
        user = get_current_user()
        if user is None or not user.has_permission('manage_marketplace'):
            return response
        content_type = response.headers.get('Content-Type', '')
        if 'text/html' not in content_type:
            return response

        try:
            services = Service.query.order_by(Service.name.asc(), Service.id.asc()).all()
            fragment = render_template('marketplace_service_gallery_fragment.html', services=services)
            body = response.get_data(as_text=True)
            marker = '</body>'
            if marker in body and 'id="marketplace-gallery-manager"' not in body:
                response.set_data(body.replace(marker, fragment + marker, 1))
        except Exception:
            return response

        return response
