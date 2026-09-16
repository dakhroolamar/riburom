"""Admin-only marketplace management routes for RI BUROM."""

import re
import unicodedata

from flask import abort, flash, redirect, request, url_for

from app import add_audit
from marketplace_models import (
    PROVIDER_STATUSES,
    SERVICE_STATUSES,
    PackageItem,
    Provider,
    ProviderType,
    ProviderTypeAssignment,
    Service,
    ServiceCategory,
)
from models import db
from storage import delete_media, save_image


def _slugify(value):
    value = unicodedata.normalize('NFKD', value or '')
    value = value.encode('ascii', 'ignore').decode('ascii').lower()
    value = re.sub(r'[^a-z0-9]+', '-', value).strip('-')
    return value or 'item'


def _unique_slug(model, value, current_id=None, provider_id=None):
    base = _slugify(value)
    slug = base
    counter = 2

    while True:
        query = model.query.filter_by(slug=slug)
        if model is Service:
            query = query.filter_by(provider_id=provider_id)

        if current_id is not None:
            query = query.filter(model.id != current_id)

        if query.first() is None:
            return slug

        slug = f'{base}-{counter}'
        counter += 1


def _text(name, limit):
    value = (request.form.get(name) or '').strip()
    if len(value) > limit:
        return None
    return value


def _sync_provider_types(provider, requested_ids):
    requested = set()

    for raw_id in requested_ids:
        try:
            requested.add(int(raw_id))
        except (TypeError, ValueError):
            continue

    valid_ids = {
        row.id
        for row in ProviderType.query.filter(ProviderType.id.in_(requested)).all()
    }

    for assignment in list(provider.provider_type_assignments):
        if assignment.provider_type_id not in valid_ids:
            db.session.delete(assignment)

    existing_ids = {
        assignment.provider_type_id
        for assignment in provider.provider_type_assignments
    }

    for provider_type_id in sorted(valid_ids - existing_ids):
        db.session.add(
            ProviderTypeAssignment(
                provider_id=provider.id,
                provider_type_id=provider_type_id,
            )
        )


def _provider_target(id):
    provider = db.session.get(Provider, id)
    if provider is None:
        abort(404)
    return provider


def _provider_type_target(id):
    provider_type = db.session.get(ProviderType, id)
    if provider_type is None:
        abort(404)
    return provider_type


def _service_category_target(id):
    category = db.session.get(ServiceCategory, id)
    if category is None:
        abort(404)
    return category


def _service_target(id):
    service = db.session.get(Service, id)
    if service is None:
        abort(404)
    return service


def _save_marketplace_image(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    try:
        return save_image(file_storage)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

def register_marketplace_admin(flask_app, view_required, manage_required):
    if getattr(flask_app, '_ri_burom_marketplace_admin_registered', False):
        return

    flask_app._ri_burom_marketplace_admin_registered = True

    @flask_app.route('/workspace/marketplace/providers/create', methods=['POST'])
    @manage_required
    def marketplace_provider_create():
        name = (request.form.get('name') or '').strip()
        if not name or len(name) > 200:
            flash('Provider name is required and must be 200 characters or fewer.', 'error')
            return redirect(url_for('workspace_marketplace'))

        email = (request.form.get('email') or '').strip() or None
        phone = (request.form.get('phone') or '').strip() or None
        description = (request.form.get('description') or '').strip() or None
        status = (request.form.get('status') or 'DRAFT').strip().upper()

        if email and (len(email) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email)):
            flash('Please provide a valid provider email address.', 'error')
            return redirect(url_for('workspace_marketplace'))

        if phone and len(phone) > 40:
            flash('Provider phone number must be 40 characters or fewer.', 'error')
            return redirect(url_for('workspace_marketplace'))

        if status not in PROVIDER_STATUSES:
            flash('Invalid provider status.', 'error')
            return redirect(url_for('workspace_marketplace'))

        try:
            image_url = _save_marketplace_image(request.files.get('image'))
        except ValueError as exc:
            flash(str(exc), 'error')
            return redirect(url_for('workspace_marketplace'))

        provider = Provider(
            name=name,
            slug=_unique_slug(Provider, request.form.get('slug') or name),
            description=description,
            email=email,
            phone=phone,
            status=status,
            image_url=image_url,
            is_active=bool(request.form.get('is_active')),
        )

        db.session.add(provider)
        db.session.flush()
        _sync_provider_types(provider, request.form.getlist('provider_type_ids'))
        add_audit('created', 'provider', provider.id, provider.name)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            if image_url:
                delete_media(image_url)
            raise

        flash(f'Provider "{provider.name}" created.', 'success')
        return redirect(url_for('workspace_marketplace'))

    @flask_app.route('/workspace/marketplace/providers/<int:id>/update', methods=['POST'])
    @manage_required
    def marketplace_provider_update(id):
        provider = _provider_target(id)

        name = (request.form.get('name') or '').strip()
        if not name or len(name) > 200:
            flash('Provider name is required and must be 200 characters or fewer.', 'error')
            return redirect(url_for('workspace_marketplace'))

        email = (request.form.get('email') or '').strip() or None
        phone = (request.form.get('phone') or '').strip() or None
        description = (request.form.get('description') or '').strip() or None
        status = (request.form.get('status') or 'DRAFT').strip().upper()

        if email and (len(email) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email)):
            flash('Please provide a valid provider email address.', 'error')
            return redirect(url_for('workspace_marketplace'))

        if phone and len(phone) > 40:
            flash('Provider phone number must be 40 characters or fewer.', 'error')
            return redirect(url_for('workspace_marketplace'))

        if status not in PROVIDER_STATUSES:
            flash('Invalid provider status.', 'error')
            return redirect(url_for('workspace_marketplace'))

        old_image_url = provider.image_url
        try:
            new_image_url = _save_marketplace_image(request.files.get('image'))
        except ValueError as exc:
            flash(str(exc), 'error')
            return redirect(url_for('workspace_marketplace'))

        provider.name = name
        provider.slug = _unique_slug(
            Provider,
            request.form.get('slug') or name,
            current_id=provider.id,
        )
        provider.description = description
        if new_image_url:
            provider.image_url = new_image_url
        provider.email = email
        provider.phone = phone
        provider.status = status
        provider.is_active = bool(request.form.get('is_active'))

        _sync_provider_types(provider, request.form.getlist('provider_type_ids'))
        add_audit('updated', 'provider', provider.id, provider.name)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            if new_image_url:
                delete_media(new_image_url)
            raise
        if new_image_url and old_image_url and old_image_url != new_image_url:
            delete_media(old_image_url)

        flash(f'Provider "{provider.name}" updated.', 'success')
        return redirect(url_for('workspace_marketplace'))

    @flask_app.route('/workspace/marketplace/providers/<int:id>/delete', methods=['POST'])
    @manage_required
    def marketplace_provider_delete(id):
        provider = _provider_target(id)

        if provider.services:
            flash('Provider cannot be deleted while it has services. Deactivate it instead.', 'error')
            return redirect(url_for('workspace_marketplace'))

        name = provider.name
        old_image_url = provider.image_url
        db.session.query(ProviderTypeAssignment).filter_by(
            provider_id=provider.id
        ).delete(synchronize_session=False)
        db.session.delete(provider)
        add_audit('deleted', 'provider', id, name)
        db.session.commit()
        delete_media(old_image_url)

        flash(f'Provider "{name}" deleted.', 'success')
        return redirect(url_for('workspace_marketplace'))

    @flask_app.route('/workspace/marketplace/provider-types/create', methods=['POST'])
    @manage_required
    def marketplace_provider_type_create():
        name = (request.form.get('name') or '').strip()
        description = (request.form.get('description') or '').strip() or None

        if not name or len(name) > 120:
            flash('Provider Type name is required and must be 120 characters or fewer.', 'error')
            return redirect(url_for('workspace_marketplace'))

        provider_type = ProviderType(
            name=name,
            slug=_unique_slug(ProviderType, request.form.get('slug') or name),
            description=description,
            is_active=bool(request.form.get('is_active')),
            sort_order=int(request.form.get('sort_order') or 0),
        )
        db.session.add(provider_type)
        db.session.flush()
        add_audit('created', 'provider_type', provider_type.id, provider_type.name)
        db.session.commit()

        flash(f'Provider Type "{provider_type.name}" created.', 'success')
        return redirect(url_for('workspace_marketplace'))

    @flask_app.route('/workspace/marketplace/provider-types/<int:id>/update', methods=['POST'])
    @manage_required
    def marketplace_provider_type_update(id):
        provider_type = _provider_type_target(id)

        name = (request.form.get('name') or '').strip()
        if not name or len(name) > 120:
            flash('Provider Type name is required and must be 120 characters or fewer.', 'error')
            return redirect(url_for('workspace_marketplace'))

        provider_type.name = name
        provider_type.slug = _unique_slug(
            ProviderType,
            request.form.get('slug') or name,
            current_id=provider_type.id,
        )
        provider_type.description = (request.form.get('description') or '').strip() or None
        provider_type.is_active = bool(request.form.get('is_active'))
        provider_type.sort_order = int(request.form.get('sort_order') or 0)

        add_audit('updated', 'provider_type', provider_type.id, provider_type.name)
        db.session.commit()

        flash(f'Provider Type "{provider_type.name}" updated.', 'success')
        return redirect(url_for('workspace_marketplace'))

    @flask_app.route('/workspace/marketplace/provider-types/<int:id>/delete', methods=['POST'])
    @manage_required
    def marketplace_provider_type_delete(id):
        provider_type = _provider_type_target(id)

        if provider_type.provider_assignments:
            flash('Provider Type cannot be deleted while providers are using it.', 'error')
            return redirect(url_for('workspace_marketplace'))

        name = provider_type.name
        db.session.delete(provider_type)
        add_audit('deleted', 'provider_type', id, name)
        db.session.commit()

        flash(f'Provider Type "{name}" deleted.', 'success')
        return redirect(url_for('workspace_marketplace'))

    @flask_app.route('/workspace/marketplace/service-categories/create', methods=['POST'])
    @manage_required
    def marketplace_service_category_create():
        name = (request.form.get('name') or '').strip()
        description = (request.form.get('description') or '').strip() or None

        if not name or len(name) > 120:
            flash('Service Category name is required and must be 120 characters or fewer.', 'error')
            return redirect(url_for('workspace_marketplace'))

        category = ServiceCategory(
            name=name,
            slug=_unique_slug(ServiceCategory, request.form.get('slug') or name),
            description=description,
            is_active=bool(request.form.get('is_active')),
            sort_order=int(request.form.get('sort_order') or 0),
        )
        db.session.add(category)
        db.session.flush()
        add_audit('created', 'service_category', category.id, category.name)
        db.session.commit()

        flash(f'Service Category "{category.name}" created.', 'success')
        return redirect(url_for('workspace_marketplace'))

    @flask_app.route('/workspace/marketplace/service-categories/<int:id>/update', methods=['POST'])
    @manage_required
    def marketplace_service_category_update(id):
        category = _service_category_target(id)

        name = (request.form.get('name') or '').strip()
        if not name or len(name) > 120:
            flash('Service Category name is required and must be 120 characters or fewer.', 'error')
            return redirect(url_for('workspace_marketplace'))

        category.name = name
        category.slug = _unique_slug(
            ServiceCategory,
            request.form.get('slug') or name,
            current_id=category.id,
        )
        category.description = (request.form.get('description') or '').strip() or None
        category.is_active = bool(request.form.get('is_active'))
        category.sort_order = int(request.form.get('sort_order') or 0)

        add_audit('updated', 'service_category', category.id, category.name)
        db.session.commit()

        flash(f'Service Category "{category.name}" updated.', 'success')
        return redirect(url_for('workspace_marketplace'))

    @flask_app.route('/workspace/marketplace/service-categories/<int:id>/delete', methods=['POST'])
    @manage_required
    def marketplace_service_category_delete(id):
        category = _service_category_target(id)

        if category.services:
            flash('Service Category cannot be deleted while services use it.', 'error')
            return redirect(url_for('workspace_marketplace'))

        name = category.name
        db.session.delete(category)
        add_audit('deleted', 'service_category', id, name)
        db.session.commit()

        flash(f'Service Category "{name}" deleted.', 'success')
        return redirect(url_for('workspace_marketplace'))

    @flask_app.route('/workspace/marketplace/services/create', methods=['POST'])
    @manage_required
    def marketplace_service_create():
        provider_id = request.form.get('provider_id')
        category_id = request.form.get('category_id')
        name = (request.form.get('name') or '').strip()
        status = (request.form.get('status') or 'DRAFT').strip().upper()

        try:
            provider_id = int(provider_id)
            category_id = int(category_id)
        except (TypeError, ValueError):
            flash('A valid Provider and Service Category are required.', 'error')
            return redirect(url_for('workspace_marketplace'))

        provider = db.session.get(Provider, provider_id)
        category = db.session.get(ServiceCategory, category_id)

        if provider is None or category is None:
            flash('A valid Provider and Service Category are required.', 'error')
            return redirect(url_for('workspace_marketplace'))

        if not name or len(name) > 200:
            flash('Service name is required and must be 200 characters or fewer.', 'error')
            return redirect(url_for('workspace_marketplace'))

        if status not in SERVICE_STATUSES:
            flash('Invalid service status.', 'error')
            return redirect(url_for('workspace_marketplace'))

        try:
            image_url = _save_marketplace_image(request.files.get('image'))
        except ValueError as exc:
            flash(str(exc), 'error')
            return redirect(url_for('workspace_marketplace'))

        service = Service(
            provider=provider,
            service_category=category,
            name=name,
            slug=_unique_slug(
                Service,
                request.form.get('slug') or name,
                provider_id=provider.id,
            ),
            description=(request.form.get('description') or '').strip() or None,
            status=status,
            image_url=image_url,
            is_active=bool(request.form.get('is_active')),
        )

        db.session.add(service)
        db.session.flush()
        add_audit('created', 'service', service.id, f'{provider.name}: {service.name}')
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            if image_url:
                delete_media(image_url)
            raise

        flash(f'Service "{service.name}" created.', 'success')
        return redirect(url_for('workspace_marketplace'))

    @flask_app.route('/workspace/marketplace/services/<int:id>/update', methods=['POST'])
    @manage_required
    def marketplace_service_update(id):
        service = _service_target(id)

        try:
            provider_id = int(request.form.get('provider_id'))
            category_id = int(request.form.get('category_id'))
        except (TypeError, ValueError):
            flash('A valid Provider and Service Category are required.', 'error')
            return redirect(url_for('workspace_marketplace'))

        provider = db.session.get(Provider, provider_id)
        category = db.session.get(ServiceCategory, category_id)
        name = (request.form.get('name') or '').strip()
        status = (request.form.get('status') or 'DRAFT').strip().upper()

        if provider is None or category is None:
            flash('A valid Provider and Service Category are required.', 'error')
            return redirect(url_for('workspace_marketplace'))

        if not name or len(name) > 200:
            flash('Service name is required and must be 200 characters or fewer.', 'error')
            return redirect(url_for('workspace_marketplace'))

        if status not in SERVICE_STATUSES:
            flash('Invalid service status.', 'error')
            return redirect(url_for('workspace_marketplace'))

        old_image_url = service.image_url
        try:
            new_image_url = _save_marketplace_image(request.files.get('image'))
        except ValueError as exc:
            flash(str(exc), 'error')
            return redirect(url_for('workspace_marketplace'))

        service.provider = provider
        service.service_category = category
        service.name = name
        service.slug = _unique_slug(
            Service,
            request.form.get('slug') or name,
            current_id=service.id,
            provider_id=provider.id,
        )
        service.description = (request.form.get('description') or '').strip() or None
        service.status = status
        if new_image_url:
            service.image_url = new_image_url
        service.is_active = bool(request.form.get('is_active'))

        add_audit('updated', 'service', service.id, f'{provider.name}: {service.name}')
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            if new_image_url:
                delete_media(new_image_url)
            raise
        if new_image_url and old_image_url and old_image_url != new_image_url:
            delete_media(old_image_url)

        flash(f'Service "{service.name}" updated.', 'success')
        return redirect(url_for('workspace_marketplace'))

    @flask_app.route('/workspace/marketplace/services/<int:id>/delete', methods=['POST'])
    @manage_required
    def marketplace_service_delete(id):
        service = _service_target(id)

        package_item_count = PackageItem.query.filter_by(service_id=service.id).count()
        if package_item_count:
            flash('Service cannot be deleted while it is attached to an experience.', 'error')
            return redirect(url_for('workspace_marketplace'))

        name = service.name
        media_urls = {value for value in [service.image_url, *[image.image_url for image in service.images]] if value}
        db.session.delete(service)
        db.session.flush()
        add_audit('deleted', 'service', id, name)
        db.session.commit()
        for media_url in media_urls:
            delete_media(media_url)

        flash(f'Service "{name}" deleted.', 'success')
        return redirect(url_for('workspace_marketplace'))