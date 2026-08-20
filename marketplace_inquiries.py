"""Public marketplace service enquiry workflow."""

import re

from flask import flash, redirect, render_template, request, url_for

from marketplace_models import MarketplaceInquiry, Provider, Service
from models import db
from notifications import notify_new_enquiry


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

    @flask_app.route('/marketplace/inquiries', methods=['POST'])
    def marketplace_inquiry_create():
        provider_id_raw = (request.form.get('provider_id') or '').strip()
        service_id_raw = (request.form.get('service_id') or '').strip()

        try:
            provider_id = int(provider_id_raw)
            service_id = int(service_id_raw)
        except (TypeError, ValueError):
            flash('Please select a valid marketplace service.', 'error')
            return redirect(request.referrer or url_for('marketplace_public_index'))

        provider = Provider.query.filter(
            Provider.id == provider_id,
            Provider.is_active.is_(True),
            Provider.status.in_(PUBLIC_PROVIDER_STATUSES),
        ).first()
        service = Service.query.filter(
            Service.id == service_id,
            Service.provider_id == provider_id,
            Service.is_active.is_(True),
            Service.status.in_(PUBLIC_SERVICE_STATUSES),
        ).first()

        if provider is None or service is None:
            flash('That marketplace service is no longer available.', 'error')
            return redirect(request.referrer or url_for('marketplace_public_index'))

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

        inquiry = MarketplaceInquiry(
            provider_id=provider.id,
            service_id=service.id,
            provider_name=provider.name,
            service_name=service.name,
            category_name=service.service_category.name,
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
        db.session.commit()

        notification_lines = [
            'Marketplace service enquiry',
            '',
            f'Provider: {provider.name}',
            f'Service: {service.name}',
            f'Category: {service.service_category.name}',
            f'Category family: {_category_family(service)}',
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

        notify_new_enquiry({
            'name': name,
            'email': email,
            'phone': phone,
            'tour_interest': f'Marketplace — {provider.name} — {service.name}',
            'message': '\n'.join(notification_lines),
            'notification_email': provider.email,
            'notification_phone': provider.phone,
        })

        return render_template(
            'marketplace_inquiry_success.html',
            inquiry=inquiry,
            provider=provider,
            service=service,
        )
