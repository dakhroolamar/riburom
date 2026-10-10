"""Validated operational input while preserving established public package fields."""
import re
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace


def editor_draft(package, form):
    values = {key: form.get(key, getattr(package, key, '') or '') for key in
              ('title', 'description', 'location', 'duration', 'price', 'category', 'best_season', 'difficulty', 'itinerary', 'included', 'excluded', 'sort_order')}
    values.update({key: getattr(package, key, None) for key in ('id', 'slug', 'image_file', 'pdf_file')})
    values.update(published=bool(form.get('published')), featured=bool(form.get('featured')))
    return SimpleNamespace(**values)


def editor_values(package):
    price = (package.price or '') if package else ''
    match = re.fullmatch(r'(?:₹\s*)?([\d,]+(?:\.\d{1,2})?)(?:\s*(?:/|per)\s*(person|group|pax))?', price, re.I)
    duration = re.fullmatch(r'(\d+)\s*(?:N|Nights?)\s*[/· ]+\s*(\d+)\s*(?:D|Days?)', (package.duration or '') if package else '', re.I)
    return dict(price_amount=match.group(1).replace(',', '') if match else '',
                price_basis='group' if match and (match.group(2) or '').lower() == 'group' else 'person',
                price_mode='amount' if match else 'request' if not price or price.lower() == 'price on request' else 'legacy',
                nights=duration.group(1) if duration else '', days=duration.group(2) if duration else '')


def package_input(form):
    values = {key: (form.get(key) or '').strip() for key in
              ('title', 'description', 'location', 'duration', 'price', 'category', 'best_season', 'difficulty', 'itinerary', 'included', 'excluded')}
    if not values['title'] or not values['description']:
        raise ValueError('Package name and overview are required.')
    limits = dict(title=200, location=200, duration=100, price=100, category=100, best_season=200, difficulty=50,
                  description=10000, itinerary=20000, included=10000, excluded=10000)
    if any(len(values[key]) > limit for key, limit in limits.items()):
        raise ValueError('A package field is too long. Shorten it before saving.')
    if 'price_mode' in form:
        mode = form.get('price_mode')
        if mode == 'request':
            values['price'] = 'Price on request'
        elif mode == 'amount':
            try:
                amount = Decimal(form.get('price_amount', ''))
                if not amount.is_finite() or amount <= 0 or amount > 999999999 or amount.as_tuple().exponent < -2:
                    raise ValueError
            except (InvalidOperation, ValueError):
                raise ValueError('Enter a positive starting price with up to two decimal places.')
            basis = form.get('price_basis')
            if basis not in ('person', 'group'):
                raise ValueError('Choose per person or per group pricing.')
            values['price'] = f'₹ {amount:,.2f} per {basis}'
        elif mode != 'legacy':
            raise ValueError('Choose a pricing option.')
    if form.get('days') or form.get('nights'):
        try:
            days, nights = int(form.get('days', '')), int(form.get('nights', ''))
            if not 1 <= days <= 365 or not 0 <= nights <= 364 or days != nights + 1:
                raise ValueError
        except ValueError:
            raise ValueError('Duration must have one more day than nights, up to 365 days.')
        values['duration'] = f'{nights} Nights / {days} Days'
    try:
        values['sort_order'] = int(form.get('sort_order') or 0)
    except ValueError:
        raise ValueError('Sort order must be a whole number.')
    return values


def readiness(package):
    return [label for field, label in (('location', 'destination'), ('duration', 'duration'), ('price', 'price'),
            ('itinerary', 'itinerary'), ('included', 'inclusions'), ('excluded', 'exclusions')) if not getattr(package, field, None)]
