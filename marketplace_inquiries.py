"""Public marketplace service enquiry workflow."""

import json
import re

from flask import flash, redirect, render_template, request, url_for

from marketplace_models import MarketplaceInquiry, Provider, Service
from models import db
from notifications import dispatch_notification_outbox, enqueue_new_enquiry


PUBLIC_PROVIDER_STATUSES = {'APPROVED', 'PUBLISHED', 'ACTIVE'}
PUBLIC_SERVICE_STATUSES = {'PUBLISHED', 'ACTIVE'}

_FIELD_LIMITS = {
    'travel_date': 120,
    'return_date': 120,
    'pickup_location': 300,
    'drop_location': 300,
    'check_in': 120,
    'check_out': 120,
    'language': 120,
    'duration': 120,
    'requirements': 10000,
}


def _clean(name, limit=None):
    value = (request.form.get(name) or '').strip()
    if limit is not None and len(value) > limit:
        return None
    return value or None


def _positive_int(name, maximum=999):
    raw = (request.form.get(name) or '').strip()
    if not raw:
        return None, None
    try:
        value = int(raw)
    except ValueError:
        return None, f'{name.replace("_", " ").title()} must be a whole number.'
    if value < 1 or value > maximum:
        return None, f'{name.replace("_", " ").title()} must be between 1 and {maximum}.'
    return value, None


def _category_family(service):
    value = f'{service.service_category.slug} {service.service_category.name}'.lower()
    if any(word in value for word in ('transport', 'taxi', 'driver', 'vehicle', 'transfer', 'rental')):
        return 'transport'
    if any(word in value for word in ('homestay', 'hotel', 'resort', 'accommodation', 'lodge', 'stay')):
        return 'accommodation'
    if any(word in value for word in ('guide', 'guiding')):
        return 'guide'
    if any(word in value for word in ('camp', 'camping')):
        return 'camping'
    if any(word in value for word in ('restaurant', 'food', 'dining', 'cafe')):
        return 'dining'
    if any(word in value for word in ('experience', 'village', 'tour', 'activity', 'adventure')):
        return 'experience'
    return 'general'


def register_marketplace_inquiries(flask_app):
    if getattr(flask_app, '_ri_burom_marketplace_inquiries_registered', False):
        return
    flask_app._ri_burom_marketplace_inquiries_registered = True

    from app import get_site_settings, limiter

    @flask_app.route('/marketplace/inquiries', methods=['POST'])
    @limiter.limit('5 per minute')
    def marketplace_inquiry_create():
        provider_id_raw = (request.form.get('provider_id') or '').strip()

        try:
            provider_id = int(provider_id_raw)
        except (TypeError, ValueError):
            flash('Please select a valid marketplace provider.', 'error')
            return redirect(request.referrer or url_for('marketplace_public_index'))

        provider = Provider.query.filter(
            Provider.id == provider_id,
            Provider.is_active.is_(True),
            Provider.status.in_(PUBLIC_PROVIDER_STATUSES),
        ).first()
        if provider is None:
            flash('That marketplace provider is no longer available.', 'error')
            return redirect(request.referrer or url_for('marketplace_public_index'))

        selected_raw = request.form.getlist('service_ids')
        selected_ids = []
        for raw in selected_raw:
            try:
                service_id = int(raw)
            except (TypeError, ValueError):
                continue
            if service_id not in selected_ids:
                selected_ids.append(service_id)

        services = []
        if selected_ids:
            services = Service.query.filter(
                Service.provider_id == provider.id,
                Service.id.in_(selected_ids),
                Service.is_active.is_(True),
                Service.status.in_(PUBLIC_SERVICE_STATUSES),
            ).all()
            services.sort(key=lambda service: selected_ids.index(service.id))
            if len(services) != len(selected_ids):
                flash('One or more selected services are no longer available. Please review your selection.', 'error')
                return redirect(url_for('marketplace_public_provider', slug=provider.slug))

        name = _clean('name')
        email = _clean('email')
        phone = _clean('phone')

        if not name or len(name) > 200:
            flash('Please provide your name.', 'error')
            return redirect(url_for('marketplace_public_provider', slug=provider.slug))
        if not email or len(email) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
            flash('Please provide a valid email address.', 'error')
            return redirect(url_for('marketplace_public_provider', slug=provider.slug))
        if phone and len(phone) > 40:
            flash('Phone / WhatsApp number is too long.', 'error')
            return redirect(url_for('marketplace_public_provider', slug=provider.slug))

        values = {}
        for field, limit in _FIELD_LIMITS.items():
            value = _clean(field, limit)
            if value is None and request.form.get(field):
                flash(f'{field.replace("_", " ").title()} is too long.', 'error')
                return redirect(url_for('marketplace_public_provider', slug=provider.slug))
            values[field] = value

        travellers, error = _positive_int('travellers', 999)
        if error:
            flash(error, 'error')
            return redirect(url_for('marketplace_public_provider', slug=provider.slug))
        rooms, error = _positive_int('rooms', 100)
        if error:
            flash(error, 'error')
            return redirect(url_for('marketplace_public_provider', slug=provider.slug))
        nights, error = _positive_int('nights', 365)
        if error:
            flash(error, 'error')
            return redirect(url_for('marketplace_public_provider', slug=provider.slug))

        selected_service_payload = [
            {
                'id': service.id,
                'name': service.name,
                'category': service.service_category.name if service.service_category else 'Marketplace service',
                'category_family': _category_family(service),
            }
            for service in services
        ]
        selected_service_names = [item['name'] for item in selected_service_payload]
        selected_categories = [item['category'] for item in selected_service_payload]

        primary_service = services[0] if services else None
        service_name = primary_service.name if primary_service else 'General provider enquiry'
        if len(selected_service_names) > 1:
            service_name = f'{service_name} + {len(selected_service_names) - 1} more'
        category_name = primary_service.service_category.name if primary_service and primary_service.service_category else 'Provider enquiry'
        if len(selected_categories) > 1:
            category_name = 'Multiple service categories'

        inquiry = MarketplaceInquiry(
            provider_id=provider.id,
            service_id=primary_service.id if primary_service else None,
            provider_name=provider.name,
            service_name=service_name,
            category_name=category_name,
            selected_services_json=json.dumps(selected_service_payload, ensure_ascii=False),
            name=name,
            email=email,
            phone=phone,
            travel_date=values['travel_date'],
            return_date=values['return_date'],
            travellers=travellers,
            pickup_location=values['pickup_location'],
            drop_location=values['drop_location'],
            check_in=values['check_in'],
            check_out=values['check_out'],
            rooms=rooms,
            nights=nights,
            language=values['language'],
            duration=values['duration'],
            requirements=values['requirements'],
            status='NEW',
        )
        db.session.add(inquiry)
        db.session.flush()

        service_lines = selected_service_names or ['General provider enquiry']
        notification_lines = [
            'Marketplace enquiry',
            '',
            f'Provider: {provider.name}',
            f'Selected service(s): {", ".join(service_lines)}',
            f'Category: {category_name}',
            '',
            f'Traveller: {name}',
            f'Email: {email}',
            f'Phone / WhatsApp: {phone or "Not provided"}',
            f'Travel date: {values["travel_date"] or "Not provided"}',
            f'Return date: {values["return_date"] or "Not provided"}',
            f'Travellers: {travellers or "Not provided"}',
            f'Pickup: {values["pickup_location"] or "Not provided"}',
            f'Drop: {values["drop_location"] or "Not provided"}',
            f'Check-in: {values["check_in"] or "Not provided"}',
            f'Check-out: {values["check_out"] or "Not provided"}',
            f'Rooms: {rooms or "Not provided"}',
            f'Nights: {nights or "Not provided"}',
            f'Language: {values["language"] or "Not provided"}',
            f'Duration: {values["duration"] or "Not provided"}',
            '',
            'Traveller requirements:',
            values['requirements'] or 'No additional requirements provided.',
            '',
            f'Inquiry ID: {inquiry.id}',
        ]

        settings = get_site_settings()
        outbox_ids = enqueue_new_enquiry(
            {
                'name': name,
                'email': email,
                'phone': phone,
                'tour_interest': f'Marketplace — {provider.name} — {", ".join(service_lines)}',
                'message': '\n'.join(notification_lines),
                'notification_email': settings.footer_email,
                'notification_phone': provider.phone,
            },
            source_type='marketplace_inquiry',
            source_id=inquiry.id,
        )
        db.session.commit()
        dispatch_notification_outbox(outbox_ids)

        return render_template(
            'marketplace_inquiry_success.html',
            inquiry=inquiry,
            provider=provider,
            service=primary_service,
        )
