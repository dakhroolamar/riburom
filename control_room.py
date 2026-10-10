"""Unified Control Room views and authenticated operational workflows."""
import csv
from copy import deepcopy
import io
import json
import os
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps
from types import SimpleNamespace

from flask import abort, flash, jsonify, redirect, render_template, request, send_file, url_for, g
from sqlalchemy import func, or_, case, select, literal, union_all, update
from sqlalchemy.orm import selectinload, undefer
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

from models import db, User, Message, Package, AuditLog
from marketplace_models import Provider, Service, ServiceCategory, ProviderType, MarketplaceInquiry
from cms_media_models import MediaAsset
from control_room_models import (
    LeadWorkspace, Trip, TripUpdate, Quote, PartnerDocument, WebsiteRevision,
    ControlPreference, Invoice, AssetMetadata, LibraryVideo, ServiceInventory,
)

TITLES = {
    'overview': ('Dashboard Overview', 'Your operations command centre for seamless travel experiences.'),
    'enquiries': ('Enquiry Work Desk', 'Accept incoming work, track next steps and follow-ups, then close or reopen each enquiry.'),
    'trips': ('Trips & Operations', 'Plan. Monitor. Deliver extraordinary travel experiences across Meghalaya.'),
    'marketplace': ('Marketplace Inventory', 'Manage and showcase Meghalaya’s authentic travel experiences.'),
    'partners': ('Partner Network', 'Our trusted network of local partners powering meaningful travel across Meghalaya.'),
    'website': ('Website Manager', 'Create, manage and publish your digital presence. Showcase Meghalaya’s extraordinary travel experiences.'),
    'media': ('Media Library', 'Manage and organize your digital assets for Meghalaya’s travel experiences.'),
    'settings': ('Settings & System', 'Manage your organisation, team, security and system preferences.'),
}
LEAD_STATES = ('NEW', 'CONTACTED', 'IN_PROGRESS', 'QUOTED', 'CONFIRMED', 'DECLINED', 'CLOSED')
TRIP_STATES = ('PLANNED', 'CONFIRMED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')
CHECKLIST = ('Vehicle assigned and inspected', 'Guide briefed on itinerary', 'Accommodation confirmed',
             'Emergency contact shared with group', 'Check-in with guide (Day 1)')


def user():
    from app import get_current_user
    return get_current_user()


def allowed(*permissions):
    person = user()
    return bool(person and (person.role == 'owner' or any(person.has_permission(p) for p in permissions)))


def revision_payload(values, home, cfg):
    """Record only edited fields and their original values for safe rebasing."""
    changed = {key: value for key, value in values.items() if value != cfg['content'].get(key, '')}
    base = {'content': {key: cfg['content'].get(key, '') for key in changed}}
    if home != cfg['home']:
        base['home'] = deepcopy(cfg['home'])
    return {'content': changed, 'home': home, '_base': base}


def apply_revision(cfg, payload):
    cfg['content'].update(payload['content'])
    if '_base' not in payload or 'home' in payload['_base']:
        cfg['home'] = payload['home']
    return cfg


def list_page(query, ordering, name, label, context):
    page_number = max(1, request.args.get(name + '_page', 1, type=int) or 1)
    result = query.order_by(*ordering).paginate(page=page_number, per_page=40, error_out=False)
    links = {}
    for direction, number in (('previous', page_number - 1), ('next', page_number + 1)):
        args = request.args.to_dict()
        args[name + '_page'] = number
        links[direction] = url_for('control_room', section=context['section'], **args)
    context.setdefault('list_pages', []).append(dict(label=label, page=page_number, pages=max(1, result.pages),
        total=result.total, has_previous=result.has_prev, has_next=result.has_next, **links))
    return result.items


def require(*permissions):
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not user():
                return redirect(url_for('admin_login', next=request.path))
            if permissions and not allowed(*permissions):
                abort(403)
            return fn(*args, **kwargs)
        return wrapped
    return decorate


def text(name, limit=1000, required=False):
    value = request.form.get(name, '').strip()
    if len(value) > limit or (required and not value):
        abort(400, description=f'Please provide a valid {name.replace("_", " ")}.')
    return value


def money(name):
    try:
        value = Decimal(request.form.get(name, '0')).quantize(Decimal('.01'))
        if not value.is_finite() or value <= 0 or value > Decimal('9999999999.99'):
            raise ValueError
        return value
    except (InvalidOperation, ValueError):
        abort(400, description='Enter a positive amount.')


def day(name, optional=False):
    try:
        value = request.form.get(name, '')
        return None if optional and not value else date.fromisoformat(value)
    except ValueError:
        abort(400, description='Enter a valid date.')


def save(target, page, message):
    from app import add_audit
    add_audit('updated', target.__tablename__, getattr(target, 'id', ''), message)
    db.session.commit()
    flash(message, 'success')
    selected = f'{target.source}-{target.source_id}' if isinstance(target, LeadWorkspace) else getattr(target, 'id', None)
    if isinstance(target, Quote):
        selected=f'{target.lead.source}-{target.lead.source_id}'
    elif isinstance(target, PartnerDocument):
        selected=target.provider_id
    return redirect(url_for('control_room', section=page, selected=selected))


def lead_record(source, source_id, create=False):
    if source == 'website':
        if not allowed('view_messages', 'manage_messages'):
            abort(403)
        obj = db.get_or_404(Message, source_id)
    elif source == 'marketplace':
        if not allowed('view_marketplace_inquiries', 'manage_marketplace_inquiries'):
            abort(403)
        obj = db.get_or_404(MarketplaceInquiry, source_id)
    else:
        abort(404)
    state = LeadWorkspace.query.filter_by(source=source, source_id=source_id).first()
    if create and not state:
        state = LeadWorkspace(source=source, source_id=source_id,
                              status=(obj.status if source == 'marketplace' else ('CONTACTED' if obj.is_read else 'NEW')))
        db.session.add(state)
        db.session.flush()
    return obj, state


def lead_item(obj, source, state=None):
    return SimpleNamespace(id=obj.id, source=source, key=f'{source}-{obj.id}', name=obj.name,
        email=obj.email, phone=obj.phone or '', travellers=obj.travellers or '',
        destination=(obj.tour_interest if source == 'website' else obj.pickup_location) or 'Not specified',
        dates=(obj.travel_dates if source == 'website' else obj.travel_date) or 'Not specified',
        message=(obj.message if source == 'website' else obj.requirements) or '',
        status=state.status if state else (obj.status if source == 'marketplace' else ('CONTACTED' if obj.is_read else 'NEW')),
        assigned=state.assigned_user if state else None, notes=state.notes if state else '',
        budget=state.budget if state else None, created_at=obj.created_at,
        updated_at=state.updated_at if state else obj.created_at, state=state)


def lead_queries(filtered=True):
    search = request.args.get('q', '').strip()[:200]
    status = request.args.get('status', 'ACTIVE')
    for source, model, perms in (
        ('website', Message, ('view_messages', 'manage_messages')),
        ('marketplace', MarketplaceInquiry, ('view_marketplace_inquiries', 'manage_marketplace_inquiries')),
    ):
        if not allowed(*perms):
            continue
        query = db.session.query(model, LeadWorkspace).outerjoin(LeadWorkspace,
            (LeadWorkspace.source == source) & (LeadWorkspace.source_id == model.id))
        if filtered and search:
            destination = model.pickup_location if source == 'marketplace' else model.tour_interest
            query = query.filter(or_(model.name.ilike(f'%{search}%'), model.email.ilike(f'%{search}%'), destination.ilike(f'%{search}%'), LeadWorkspace.notes.ilike(f'%{search}%')))
        default_state = model.status if source == 'marketplace' else case((model.is_read.is_(True), 'CONTACTED'), else_='NEW')
        if filtered and status == 'ACTIVE':
            query = query.filter(func.coalesce(LeadWorkspace.status, default_state).notin_(['CLOSED','DECLINED']))
        if filtered and status in LEAD_STATES:
            query = query.filter(func.coalesce(LeadWorkspace.status, default_state) == status)
        yield source, model, query, func.coalesce(LeadWorkspace.status, default_state)


def leads(page=1):
    queries = list(lead_queries())
    if not queries:
        return [], 0
    selections = [query.with_entities(model.id.label('id'), model.created_at.label('created_at'), literal(source).label('source')).statement
                  for source, model, query, state in queries]
    combined = union_all(*selections).subquery()
    total = db.session.scalar(select(func.count()).select_from(combined))
    keys = db.session.execute(select(combined).order_by(combined.c.created_at.desc(), combined.c.id.desc()).limit(50).offset((page-1)*50)).all()
    items = {}
    for source, model, query, state in queries:
        ids = [key.id for key in keys if key.source == source]
        if ids:
            for obj, metadata in query.options(selectinload(LeadWorkspace.assigned_user), undefer(LeadWorkspace.next_action), undefer(LeadWorkspace.follow_up)).filter(model.id.in_(ids)).all():
                items[(source, obj.id)] = lead_item(obj, source, metadata)
    return [items[(key.source, key.id)] for key in keys], total


def lead_counts():
    counts = dict.fromkeys(LEAD_STATES, 0)
    for source, model, query, state in lead_queries(False):
        for value, count in query.with_entities(state, func.count(model.id)).group_by(state).all():
            if value in counts:
                counts[value] += count
    return counts


def navigation():
    checks = {'overview': (), 'enquiries': ('view_messages', 'manage_messages', 'view_marketplace_inquiries', 'manage_marketplace_inquiries'),
        'trips': ('manage_tours',), 'marketplace': ('view_marketplace', 'manage_marketplace', 'manage_tours'),
        'partners': ('view_marketplace', 'manage_marketplace'), 'website': ('manage_about', 'manage_media', 'manage_structure'),
        'media': ('manage_media',), 'settings': ('manage_users',)}
    return [(key, {'overview': 'Overview', 'website': 'Website', 'media': 'Media', 'settings': 'Settings'}.get(key, key.title()))
            for key, perms in checks.items() if not perms or allowed(*perms)]


def register_control_room(app):
    from app import get_site_settings, get_public_config, add_audit
    from cms_pages import PAGES, CONTENT, HOME, COLLECTIONS
    from config_concurrency import public_config_token, public_config_token_matches

    @app.context_processor
    def control_context():
        return {'control_nav': navigation() if user() else [], 'control_allowed': allowed,
                'control_today': date.today(), 'control_checklist': CHECKLIST}

    @app.route('/workspace/control/search')
    @require()
    def control_search():
        term=request.args.get('q','').strip()[:200]
        results=[]
        if term:
            rows,total=leads()
            results.extend(dict(label=row.name,detail=row.destination,area='Enquiries',href=url_for('control_room',section='enquiries',selected=row.key)) for row in rows[:20])
            for model,permissions,field,area,section in (
                (Trip,('manage_tours',),'name','Trips','trips'),
                (Provider,('view_marketplace','manage_marketplace'),'name','Partners','partners'),
                (Service,('view_marketplace','manage_marketplace'),'name','Marketplace','marketplace'),
                (Package,('manage_tours','view_marketplace'),'title','Packages','marketplace')):
                if allowed(*permissions):
                    for item in model.query.filter(getattr(model,field).ilike(f'%{term}%')).limit(10).all():
                        results.append(dict(label=getattr(item,field),detail=area,area=area,href=url_for('control_room',section=section,selected=item.id)))
            if allowed('manage_about','manage_media','manage_structure'):
                results.extend(dict(label=label,detail='Website area',area='Website',href=url_for('control_room',section='website',page=key)) for key,label in PAGES.items() if term.lower() in label.lower())
        return render_template('control_room/search.html',section='overview',title='Search Results',term=term,results=results)

    @app.route('/workspace/control/<section>')
    @require()
    def control_room(section):
        if section not in dict(navigation()):
            abort(403 if section in TITLES else 404)
        context = dict(section=section, title=TITLES[section][0], subtitle=TITLES[section][1],
                       settings=get_site_settings(), today=date.today(), selected=None, stats=[])
        if section == 'enquiries':
            page_number = max(1, request.args.get('page', 1, type=int) or 1)
            rows, total = leads(page_number)
            context.update(leads=rows, staff=User.query.filter_by(is_active=True).order_by(User.full_name).all(),
                           counts=lead_counts(), lead_total=total, page_number=page_number,
                           page_count=max(1, (total+49)//50))
            key = request.args.get('selected', '')
            context['selected'] = next((row for row in rows if row.key == key), rows[0] if rows else None)
            if key:
                source, separator, source_id = key.partition('-')
                if not separator or not source_id.isdigit():
                    abort(400)
                obj,state=lead_record(source,int(source_id))
                context['selected']=lead_item(obj,source,state)
            selected = context['selected']
            context['lead_history'] = AuditLog.query.filter_by(target_type='control_leads', target_id=str(selected.state.id)).order_by(AuditLog.id.desc()).limit(30).all() if selected and selected.state else []
            context['quotes'] = Quote.query.filter_by(lead_id=selected.state.id).order_by(Quote.id.desc()).limit(20).all() if selected and selected.state else []
            context['stats'] = [('users', context['counts']['NEW'], 'New Leads', 'green'),
                                ('clock', context['counts']['CONTACTED'], 'Contacted', 'sand'),
                                ('file', context['counts']['QUOTED'], 'Quoted Enquiries', 'blue'),
                                ('chart', context['counts']['CONFIRMED'], 'Confirmed', 'sand')]
        if section == 'trips':
            query = Trip.query
            q = request.args.get('q', '')[:200]
            if section == 'trips' and q:
                query = query.filter(or_(Trip.name.ilike(f'%{q}%'), Trip.destination.ilike(f'%{q}%'), Trip.guide.ilike(f'%{q}%'), Trip.vehicle.ilike(f'%{q}%')))
            if section == 'trips' and request.args.get('date'):
                try:
                    query = query.filter(Trip.start_date == date.fromisoformat(request.args['date']))
                except ValueError:
                    abort(400)
            if request.args.get('status') in TRIP_STATES:
                query = query.filter_by(status=request.args['status'])
            context['trips'] = list_page(query, (Trip.start_date.desc(), Trip.id.desc()), 'trips', 'Trips', context) if allowed('manage_tours') else []
            context['upcoming'] = Trip.query.filter(Trip.start_date >= date.today(), Trip.status != 'CANCELLED').order_by(Trip.start_date).limit(20).all() if allowed('manage_tours') else []
            if section == 'trips':
                context['selected'] = next((t for t in context['trips'] if str(t.id) == request.args.get('selected')), context['trips'][0] if context['trips'] else None)
                if request.args.get('selected','').isdigit():
                    context['selected']=db.get_or_404(Trip,int(request.args['selected']))
                chosen = context['selected']
                context.update(itinerary=json.loads(chosen.itinerary_json) if chosen else [],
                               accommodation=json.loads(chosen.accommodation_json) if chosen else [],
                               checklist=json.loads(chosen.checklist_json) if chosen else {},
                               updates=TripUpdate.query.filter_by(trip_id=chosen.id).order_by(TripUpdate.id.desc()).limit(20).all() if chosen else [],
                               departures=[date.today() + timedelta(days=i) for i in range(14)])
                context['stats'] = [('calendar', Trip.query.filter(Trip.start_date >= date.today(), Trip.status.in_(['PLANNED', 'CONFIRMED'])).count(), 'Upcoming Departures', 'green'),
                                    ('walk', Trip.query.filter_by(status='IN_PROGRESS').count(), 'Trips On Ground', 'sand'),
                                    ('file', Trip.query.filter_by(itinerary_json='[]').count(), 'Pending Itineraries', 'sand'),
                                    ('check', Trip.query.filter(Trip.status == 'COMPLETED', Trip.end_date >= date.today().replace(day=1)).count(), 'Completed This Month', 'green')]
        if section in ('partners', 'marketplace'):
            can = allowed('view_marketplace', 'manage_marketplace')
            partner_query = Provider.query.options(selectinload(Provider.provider_type_assignments))
            if section == 'partners':
                q = request.args.get('q','')[:200]
                if q:
                    partner_query = partner_query.filter(Provider.name.ilike(f'%{q}%'))
                kind = request.args.get('type','')
                if kind:
                    if not kind.isdigit():
                        abort(400)
                    partner_query = partner_query.filter(Provider.provider_type_assignments.any(provider_type_id=int(kind)))
            context['partners'] = list_page(partner_query, (Provider.name, Provider.id), 'partners', 'Partners', context) if can else []
            context['partner_total'] = partner_query.count() if can else 0
            context['pending_count'] = Provider.query.filter(Provider.status.in_(['SUBMITTED','UNDER_REVIEW'])).count() if can else 0
            context['pending_partners'] = [p for p in context['partners'] if p.status in ('SUBMITTED', 'UNDER_REVIEW')]
            if section == 'partners':
                selected = next((p for p in context['partners'] if str(p.id) == request.args.get('selected')), context['pending_partners'][0] if context['pending_partners'] else (context['partners'][0] if context['partners'] else None))
                if request.args.get('selected','').isdigit():
                    selected=db.get_or_404(Provider,int(request.args['selected']))
                context.update(selected=selected, documents=PartnerDocument.query.filter_by(provider_id=selected.id).order_by(PartnerDocument.id.desc()).limit(100).all() if selected and allowed('manage_marketplace') else [],
                               provider_types=ProviderType.query.order_by(ProviderType.name).all())
                context['stats'] = [('users', Provider.query.filter(Provider.status.in_(['VERIFIED', 'APPROVED', 'PUBLISHED', 'ACTIVE'])).count(), 'Verified Partners', 'green'),
                                    ('clock', context['pending_count'], 'Pending Approvals', 'sand'),
                                    ('pin', ProviderType.query.count(), 'Partner Types', 'blue'),
                                    ('file', PartnerDocument.query.filter(PartnerDocument.expires_on <= date.today() + timedelta(days=30)).count(), 'Documents Expiring Soon', 'sand')]
            if section == 'marketplace':
                service_query = Service.query.options(selectinload(Service.provider), selectinload(Service.service_category))
                if request.args.get('q'):
                    service_query = service_query.filter(Service.name.ilike('%' + request.args['q'][:200] + '%'))
                context['services'] = list_page(service_query, (Service.updated_at.desc(), Service.id.desc()), 'services', 'Experiences', context) if can else []
                ids = [s.id for s in context['services']]
                context['inventory'] = {i.service_id:i for i in ServiceInventory.query.filter(ServiceInventory.service_id.in_(ids)).all()} if ids else {}
                context['partner_groups'] = {key:[p for p in context['partners'] if any(key in a.provider_type.name.lower() for a in p.provider_type_assignments)] for key in ('homestay','guide','driver','vehicle')}
                context['packages'] = list_page(Package.query, (Package.updated_at.desc(), Package.id.desc()), 'packages', 'Packages', context)
                context['partner_choices'] = db.session.query(Provider.id, Provider.name).order_by(Provider.name).all() if allowed('manage_marketplace') else []
                context['categories'] = ServiceCategory.query.order_by(ServiceCategory.name).all()
                context['provider_types'] = ProviderType.query.order_by(ProviderType.name).all()
                context['stats'] = [('walk', Service.query.filter(Service.status.in_(['ACTIVE', 'PUBLISHED']), Service.is_active.is_(True)).count(), 'Active Experiences', 'green'),
                                    ('box', Package.query.count(), 'Packages', 'sand'),
                                    ('home', Provider.query.count(), 'Partners', 'sand'),
                                    ('users', ProviderType.query.count(), 'Partner Types', 'blue')]
        if section == 'overview':
            context['counts'] = lead_counts()
            context['upcoming'] = Trip.query.filter(Trip.start_date >= date.today(), Trip.status != 'CANCELLED').order_by(Trip.start_date).limit(7).all() if allowed('manage_tours') else []
            pending = Provider.query.filter(Provider.status.in_(['SUBMITTED', 'UNDER_REVIEW']))
            context['pending_count'] = pending.count() if allowed('view_marketplace', 'manage_marketplace') else 0
            context['pending_partners'] = pending.order_by(Provider.created_at).limit(4).all() if allowed('view_marketplace', 'manage_marketplace') else []
            prefs = db.session.get(ControlPreference, 'notifications')
            context['notifications'] = json.loads(prefs.value_json) if prefs else {}
            context['activity'] = TripUpdate.query.options(selectinload(TripUpdate.author)).order_by(TripUpdate.created_at.desc()).limit(5).all() if allowed('manage_tours') and context['notifications'].get('trip_updates',True) else []
            context['publishing_activity'] = WebsiteRevision.query.filter(WebsiteRevision.published_at.is_not(None), WebsiteRevision.is_backup.is_(False)).order_by(WebsiteRevision.published_at.desc()).limit(5).all() if allowed('manage_about') and context['notifications'].get('marketing_updates',False) else []
            context['stats'] = [('users', context['counts']['NEW'], 'New Enquiries', 'green'),
                ('calendar', Trip.query.filter(Trip.start_date >= date.today(),Trip.status!='CANCELLED').count() if allowed('manage_tours') else '—', 'Upcoming Trips', 'blue'),
                ('users', context['pending_count'], 'Partner Approvals', 'sand'),
                ('box', Package.query.filter_by(published=True).count() if allowed('manage_tours', 'view_marketplace') else '—', 'Active Packages', 'slate')]
        if section == 'website':
            page = request.args.get('page', 'home')
            if page == 'reviews':
                if not allowed('manage_about'):
                    abort(403)
                from models import TravellerReview
                context['reviews'] = list_page(TravellerReview.query, (TravellerReview.created_at.desc(), TravellerReview.id.desc()), 'reviews', 'Reviews', context)
                return render_template('control_room/reviews.html', **context)
            if page == 'stories':
                if not allowed('manage_about'):
                    abort(403)
                return render_template('control_room/blog.html', **context)
            if page not in PAGES:
                abort(404)
            revisions = WebsiteRevision.query.filter_by(page=page).order_by(WebsiteRevision.id.desc()).limit(20).all()
            cfg = get_public_config(context['settings'])
            latest = revisions[0] if revisions and not revisions[0].published_at and not revisions[0].is_backup else None
            payload = json.loads(latest.payload_json) if latest else {'content': cfg['content'], 'home': cfg['home']}
            section_keys = {'home': ['hero', 'home_about_gallery', 'home_tours', 'home_why', 'home_blog', 'home_contact'], 'footer': ['footer_partners']}.get(page, [page])
            fields = list(dict.fromkeys(name for key in section_keys for name in CONTENT.get(key, [])))
            context.update(sections=HOME if page == 'home' else [(page, PAGES[page])], collections=COLLECTIONS,
                packages=Package.query.order_by(Package.sort_order, Package.id).all() if page == 'tour-detail' else [],
                content_sections=[(dict(HOME).get(key, PAGES.get(key, key.replace('_',' ').title())), CONTENT.get(key, [])) for key in section_keys if CONTENT.get(key)],
                pages=PAGES, page=page, payload=payload, fields=fields, revisions=revisions,
                revision=latest, config_token=public_config_token(context['settings']), public=cfg,
                preview_url={'home': '/', 'tours': '/all_tours', 'marketplace': '/marketplace', 'about': '/about', 'contact': '/#contact'}.get(page, '/'))
            context['stats'] = [('file', len(PAGES), 'Website Areas', 'green'), ('file', WebsiteRevision.query.filter_by(published_at=None, is_backup=False).count(), 'Saved Drafts', 'sand'),
                                ('alert', sum(not cfg['content'].get(n) for n in ('site_title', 'meta_description')), 'SEO Fields Missing', 'rose'),
                                ('clock', WebsiteRevision.query.filter(WebsiteRevision.created_at >= datetime.utcnow() - timedelta(days=30)).count(), 'Recent Updates', 'blue')]
        if section == 'media':
            context['stats'] = [('image', MediaAsset.query.count() + LibraryVideo.query.count(), 'Total Assets', 'green'),
                                ('camera', MediaAsset.query.count(), 'Photos', 'sand'),
                                ('video', LibraryVideo.query.count(), 'Videos', 'blue'),
                                ('database', f'{((db.session.query(func.sum(MediaAsset.byte_size)).scalar() or 0) + (db.session.query(func.sum(LibraryVideo.byte_size)).scalar() or 0)) / 1048576:.1f} MB', 'Known Storage Used', 'purple')]
        if section == 'settings':
            if user().role != 'owner':
                abort(403)
            prefs = db.session.get(ControlPreference, 'notifications')
            from notifications import delivery_preferences
            context['delivery_preferences'] = delivery_preferences()
            context.update(staff=User.query.order_by(User.full_name).all(), invoices=Invoice.query.order_by(Invoice.id.desc()).limit(50).all(),
                audits=AuditLog.query.order_by(AuditLog.id.desc()).limit(20).all(), notifications=json.loads(prefs.value_json) if prefs else {},
                integrations=[('Email notifications', bool(os.getenv('BREVO_API_KEY'))), ('Media storage', bool(os.getenv('CLOUDINARY_API_KEY'))),
                              ('WhatsApp / SMS', bool(os.getenv('TWILIO_ACCOUNT_SID'))), ('IndexNow', bool(os.getenv('INDEXNOW_KEY')))],
                permission_keys=__import__('models').ROLE_PERMISSIONS['owner'])
        return render_template('control_room/page.html', **context)

    @app.route('/workspace/control/partners/<int:id>/edit')
    @require('manage_marketplace')
    def marketplace_provider_edit(id):
        return render_template('control_room/catalogue_edit.html', section='partners', title='Edit Partner', kind='partner',
            item=db.get_or_404(Provider, id), provider_types=ProviderType.query.order_by(ProviderType.name).all())

    @app.route('/workspace/control/services/<int:id>/edit')
    @require('manage_marketplace')
    def marketplace_service_edit(id):
        return render_template('control_room/catalogue_edit.html', section='marketplace', title='Edit Experience', kind='service',
            item=db.get_or_404(Service, id), inventory=db.session.get(ServiceInventory,id), partners=Provider.query.order_by(Provider.name).all(), categories=ServiceCategory.query.order_by(ServiceCategory.name).all())

    @app.route('/workspace/control/services/<int:service_id>/inventory', methods=['POST'])
    @require('manage_marketplace')
    def control_service_inventory(service_id):
        db.get_or_404(Service, service_id)
        details = db.session.get(ServiceInventory, service_id) or ServiceInventory(service_id=service_id)
        details.location = text('location', 240)
        details.price = money('price') if request.form.get('price') else None
        slots = request.form.get('available_slots', '')
        if slots and (not slots.isdigit() or int(slots)>1000000):
            abort(400, description='Enter a valid number of available slots.')
        details.available_slots = int(slots) if slots else None
        db.session.add(details)
        add_audit('updated', 'service_inventory', service_id)
        db.session.commit()
        flash('Pricing and availability saved.', 'success')
        return redirect(url_for('marketplace_service_edit',id=service_id))

    @app.route('/workspace/control/website/revisions/<int:revision_id>/preview')
    @require('manage_about')
    def control_website_preview(revision_id):
        revision = db.get_or_404(WebsiteRevision, revision_id)
        cfg = deepcopy(get_public_config(get_site_settings()))
        payload = json.loads(revision.payload_json)
        apply_revision(cfg, payload)
        arguments = {}
        if revision.page in ('tour-detail', 'provider'):
            from app import _public_provider_query
            targets = (Package.query.filter_by(published=True).order_by(Package.title).all()
                       if revision.page == 'tour-detail' else _public_provider_query().order_by(Provider.name).all())
            slug = request.args.get('slug', '')
            if not slug:
                response = app.make_response(render_template('control_room/preview_target.html', revision=revision, targets=targets))
                response.headers['Cache-Control'] = 'private, no-store'
                return response
            if not any(target.slug == slug for target in targets):
                abort(404)
            endpoint = 'tour_detail' if revision.page == 'tour-detail' else 'marketplace_public_provider'
            arguments = {'slug': slug}
        else:
            endpoint = {'home': 'home', 'tours': 'all_tours', 'about': 'about', 'contact': 'home', 'footer': 'home', 'marketplace': 'marketplace_public_index'}.get(revision.page)
            if endpoint is None:
                abort(404)
        g.control_public_preview = cfg
        try:
            response = app.make_response(app.view_functions[endpoint](**arguments))
        finally:
            g.pop('control_public_preview', None)
        response.headers['Cache-Control'] = 'private, no-store'
        return response

    @app.route('/workspace/control/media/assets')
    @require('manage_media')
    def control_media_assets():
        from cms_pages import delivery, asset_usage_batch, media_page, filter_media_usage
        query=MediaAsset.query.outerjoin(AssetMetadata,AssetMetadata.asset_id==MediaAsset.id)
        if request.args.get('asset_id'):
            asset_id = request.args.get('asset_id', type=int)
            if asset_id is None:
                abort(400)
            query = query.filter(MediaAsset.id == asset_id)
        term=request.args.get('q','').strip()[:200]
        if term:
            query=query.filter(or_(MediaAsset.title.ilike(f'%{term}%'),MediaAsset.path.ilike(f'%{term}%'),
                                   AssetMetadata.location.ilike(f'%{term}%'),AssetMetadata.tags.ilike(f'%{term}%')))
        order=MediaAsset.created_at.asc() if request.args.get('sort')=='oldest' else MediaAsset.created_at.desc()
        query = filter_media_usage(query)
        assets, pagination = media_page(query, (order, MediaAsset.id.desc()))
        usage = asset_usage_batch(assets)
        metadata = {m.asset_id: m for m in AssetMetadata.query.filter(AssetMetadata.asset_id.in_([a.id for a in assets])).all()} if assets else {}
        return jsonify(items=[dict(id=a.id, version=a.version, title=a.title, src=delivery(a.path, 400), preview_src=delivery(a.path, 1200), path=a.path,
            alt=a.alt, caption=a.caption, credit=a.credit, width=a.width, height=a.height, byte_size=a.byte_size,
            created_at=a.created_at.isoformat(), usage=usage[a.id], kind='image',
            location=metadata[a.id].location if a.id in metadata else '', category=metadata[a.id].category if a.id in metadata else '',
            tags=metadata[a.id].tags if a.id in metadata else '')
            for a in assets], **(pagination or {}))

    @app.route('/workspace/control/media/assets/<int:asset_id>/replace', methods=['POST'])
    @require('manage_media')
    def control_media_replace(asset_id):
        from storage import save_image
        from PIL import Image, UnidentifiedImageError
        asset = db.get_or_404(MediaAsset, asset_id)
        upload = request.files.get('image')
        if not upload or not upload.filename:
            return jsonify(error='Choose a photograph.'), 400
        data = upload.read(12 * 1024 * 1024 + 1)
        if len(data) > 12 * 1024 * 1024:
            return jsonify(error='Images must be no larger than 12 MB.'), 400
        try:
            with Image.open(io.BytesIO(data)) as image:
                width, height = image.size
                if width * height > 40000000 or min(width, height) < 16:
                    raise ValueError('Use an image between 16 pixels and 40 megapixels.')
                image.verify()
            upload.stream.seek(0)
            path = save_image(upload)
        except (ValueError, UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            return jsonify(error=str(exc)), 400
        # Collections refer to the ID; older editors store the path directly.
        from models import AboutContent, TeamMember, SiteSettings
        from marketplace_models import ServiceImage
        old_path = asset.path
        for model, field in ((Package,'image_file'),(AboutContent,'hero_image'),(TeamMember,'photo_file'),
                             (Provider,'image_url'),(Service,'image_url'),(ServiceImage,'image_url')):
            model.query.filter(getattr(model,field)==old_path).update({field:path},synchronize_session='fetch')
        def replace_path(value):
            if isinstance(value,dict):
                return {key:replace_path(item) for key,item in value.items()}
            if isinstance(value,list):
                return [replace_path(item) for item in value]
            return path if value==old_path else value
        settings=get_site_settings()
        for column in SiteSettings.__table__.columns:
            value=getattr(settings,column.name)
            if isinstance(value,str) and value==old_path:
                setattr(settings,column.name,path)
            elif column.name.endswith('_json') and value:
                try:
                    parsed=json.loads(value)
                    updated=replace_path(parsed)
                    if updated!=parsed:
                        setattr(settings,column.name,json.dumps(updated,ensure_ascii=False))
                except (ValueError,TypeError):
                    pass
        asset.path, asset.width, asset.height, asset.byte_size = path, width, height, len(data)
        add_audit('replaced', 'media_asset', asset.id)
        from indexnow import notify_indexnow_cms_change
        notify_indexnow_cms_change('home', stage_only=True)
        db.session.commit()
        return jsonify(id=asset.id)

    @app.route('/workspace/control/leads/<source>/<int:source_id>', methods=['POST'])
    @require()
    def control_lead_save(source, source_id):
        if not allowed('manage_messages' if source == 'website' else 'manage_marketplace_inquiries'):
            abort(403)
        obj, state = lead_record(source, source_id)
        token = request.form.get('work_token')
        if token != (state.updated_at.isoformat() if state else 'new'):
            abort(409, description='This enquiry changed. Reload before saving your update.')
        previous = lead_item(obj, source, state)
        action = request.form.get('action', 'update')
        values = dict(status=previous.status, assigned_user_id=state.assigned_user_id if state else None,
                      notes=state.notes if state else '', budget=state.budget if state else None,
                      call_at=state.call_at if state else None, next_action=state.next_action if state else '',
                      follow_up=state.follow_up if state else None, updated_at=datetime.utcnow())
        note = text('progress_note', 5000)
        if action == 'accept':
            if previous.status in ('CLOSED','DECLINED'):
                abort(400, description='Reopen this enquiry before accepting it.')
            values.update(status='IN_PROGRESS' if previous.status in ('NEW','CONTACTED') else previous.status, assigned_user_id=user().id)
        elif action == 'close':
            values['status'] = 'CLOSED'
        elif action == 'reopen':
            if previous.status not in ('CLOSED','DECLINED'):
                abort(400, description='This enquiry is already open.')
            values['status'] = 'NEW'
        elif action == 'update':
            values['status'] = request.form.get('status', previous.status)
            if values['status'] not in LEAD_STATES:
                abort(400)
            assigned = request.form.get('assigned_user_id', '')
            if assigned:
                person = db.session.get(User, int(assigned)) if assigned.isdigit() else None
                if not person or not person.is_active or not person.has_permission('manage_messages' if source=='website' else 'manage_marketplace_inquiries'):
                    abort(400, description='Choose an active enquiry team member.')
                values['assigned_user_id'] = person.id
            else:
                values['assigned_user_id'] = None
            values['notes'] = text('notes', 10000) if 'notes' in request.form else values['notes']
            values['budget'] = money('budget') if request.form.get('budget') else None
            values['next_action'] = text('next_action', 500)
            values['follow_up'] = day('follow_up', optional=True)
            try:
                values['call_at'] = datetime.fromisoformat(request.form['call_at']) if request.form.get('call_at') else None
            except ValueError:
                abort(400, description='Enter a valid call date and time.')
        else:
            abort(400)
        actor = db.session.get(User, values['assigned_user_id']) if values['assigned_user_id'] else None
        details = f'{action.title()}: {previous.status} → {values["status"]}. Assigned to: {actor.full_name if actor else "Unassigned"}.'
        details += f' Next action: {values["next_action"] or "None"}. Follow-up: {values["follow_up"] or "None"}.'
        if note:
            details += '\n' + note
        if values['notes'] != previous.notes:
            details += '\nStaff notes: ' + values['notes']
        try:
            if state:
                result = db.session.execute(update(LeadWorkspace).where(
                    LeadWorkspace.id == state.id, LeadWorkspace.updated_at == state.updated_at).values(**values))
                if result.rowcount != 1:
                    db.session.rollback()
                    abort(409, description='This enquiry changed. Reload before saving.')
            else:
                state = LeadWorkspace(source=source, source_id=source_id, **values)
                db.session.add(state)
                db.session.flush()
            if source == 'marketplace':
                obj.status = values['status']
            else:
                obj.is_read = values['status'] != 'NEW'
            add_audit('work_updated', 'control_leads', state.id, details)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            abort(409, description='This enquiry changed. Reload before saving.')
        flash('Enquiry work updated.', 'success')
        return redirect(url_for('control_room', section='enquiries', selected=f'{source}-{source_id}', status='ALL'))

    @app.route('/workspace/control/quotes/<source>/<int:source_id>', methods=['POST'])
    @require()
    def control_quote_create(source, source_id):
        if not allowed('manage_messages' if source == 'website' else 'manage_marketplace_inquiries'):
            abort(403)
        obj, lead = lead_record(source, source_id, create=True)
        quote = Quote(lead_id=lead.id, amount=money('amount'), summary=text('summary', 10000, True), valid_until=day('valid_until'))
        lead.status = 'QUOTED'
        if source == 'marketplace':
            obj.status = 'QUOTED'
        else:
            obj.is_read = True
        db.session.add(quote)
        add_audit('quote_created', 'control_leads', lead.id, 'Quote prepared. Status: QUOTED.')
        return save(quote, 'enquiries', 'Quote created. Download it to share with the traveller.')

    @app.route('/workspace/control/quotes/<int:quote_id>')
    @require()
    def control_quote_view(quote_id):
        quote = db.get_or_404(Quote, quote_id)
        obj, _ = lead_record(quote.lead.source, quote.lead.source_id)
        return render_template('control_room/document.html', heading=f'Quote RB-Q-{quote.id:05d}', customer=obj.name,
                               description=quote.summary, amount=quote.amount, deadline=quote.valid_until, settings=get_site_settings())

    @app.route('/workspace/control/trips/save', methods=['POST'])
    @require('manage_tours')
    def control_trip_save():
        trip_id = request.form.get('id')
        trip = db.get_or_404(Trip, int(trip_id)) if trip_id and trip_id.isdigit() else Trip()
        trip.name = text('name', 200, True)
        trip.destination = text('destination', 300, True)
        trip.start_date, trip.end_date = day('start_date'), day('end_date')
        if trip.end_date < trip.start_date:
            abort(400, description='The return date must follow departure.')
        trip.travellers = request.form.get('travellers', type=int) or 1
        if not 1 <= trip.travellers <= 10000:
            abort(400)
        trip.status = request.form.get('status', 'PLANNED')
        if trip.status not in TRIP_STATES:
            abort(400)
        for field in ('guide', 'driver', 'vehicle'):
            setattr(trip, field, text(field, 200))
        trip.itinerary_json = json.dumps([line.strip() for line in text('itinerary', 20000).splitlines() if line.strip()])
        trip.accommodation_json = json.dumps([line.strip() for line in text('accommodation', 10000).splitlines() if line.strip()])
        source, source_id = request.form.get('source'), request.form.get('source_id', type=int)
        if source and source_id and not trip.id:
            obj, lead = lead_record(source, source_id, create=True)
            if not allowed('manage_messages' if source == 'website' else 'manage_marketplace_inquiries'):
                abort(403)
            if Trip.query.filter_by(lead_id=lead.id).first():
                abort(409, description='This enquiry already has a trip.')
            trip.lead_id = lead.id
            lead.status = 'CONFIRMED'
            if source == 'marketplace':
                obj.status = 'CONFIRMED'
        db.session.add(trip)
        if trip.lead_id:
            add_audit('trip_updated', 'control_leads', trip.lead_id, 'Trip details saved. Enquiry linked to operational trip.')
        return save(trip, 'trips', 'Trip saved.')

    @app.route('/workspace/control/trips/<int:trip_id>/update', methods=['POST'])
    @require('manage_tours')
    def control_trip_update(trip_id):
        trip = db.get_or_404(Trip, trip_id)
        checklist = json.loads(trip.checklist_json)
        if request.form.get('action') == 'milestones':
            itinerary = json.loads(trip.itinerary_json)
            completed = request.form.getlist('completed_days')
            checklist.update({f'day:{i+1}':str(i+1) in completed for i in range(len(itinerary))})
            trip.checklist_json = json.dumps(checklist)
            return save(trip, 'trips', 'Itinerary milestones saved.')
        if request.form.get('action') == 'checklist':
            checklist.update({key: key in request.form.getlist('completed') for key in CHECKLIST})
            trip.checklist_json = json.dumps(checklist)
            return save(trip, 'trips', 'Checklist saved.')
        update = TripUpdate(trip_id=trip.id, author_id=user().id, message=text('message', 10000, True))
        db.session.add(update)
        add_audit('created', 'trip_update', trip.id, 'Field update')
        db.session.commit()
        return redirect(url_for('control_room', section='trips', selected=trip.id))

    @app.route('/workspace/control/trips/export')
    @require('manage_tours')
    def control_trip_export():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Group', 'Destination', 'Departure', 'Return', 'Guide', 'Driver', 'Vehicle', 'Status'])
        def safe_cell(value):
            value = str(value or '')
            return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value
        for trip in Trip.query.order_by(Trip.start_date).limit(10000).all():
            writer.writerow([safe_cell(value) for value in (trip.name, trip.destination, trip.start_date, trip.end_date, trip.guide, trip.driver, trip.vehicle, trip.status)])
        return app.response_class(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=trips.csv'})

    @app.route('/workspace/control/partners/<int:provider_id>/documents', methods=['POST'])
    @require('manage_marketplace')
    def control_partner_document(provider_id):
        db.get_or_404(Provider, provider_id)
        upload = request.files.get('document')
        if not upload or not upload.filename:
            abort(400, description='Choose a PDF document.')
        data = upload.read(10 * 1024 * 1024 + 1)
        if not data.startswith(b'%PDF-') or len(data) > 10 * 1024 * 1024:
            abort(400, description='Upload a PDF no larger than 10 MB.')
        document = PartnerDocument(provider_id=provider_id, kind=text('kind', 80, True),
                                  file_name=secure_filename(upload.filename)[:240] or 'document.pdf', file_data=data,
                                  expires_on=day('expires_on', optional=True))
        db.session.add(document)
        return save(document, 'partners', 'Private partner document uploaded.')

    @app.route('/workspace/control/documents/<int:document_id>', methods=['GET', 'POST'])
    @require('manage_marketplace')
    def control_document(document_id):
        document = db.get_or_404(PartnerDocument, document_id)
        if request.method == 'GET':
            response = send_file(io.BytesIO(document.file_data), mimetype='application/pdf', as_attachment=True, download_name=document.file_name)
            response.headers['Cache-Control'] = 'private, no-store'
            return response
        document.status = request.form.get('status')
        if document.status not in ('VERIFIED', 'REJECTED', 'UNDER_REVIEW'):
            abort(400)
        document.review_note = text('review_note', 5000)
        document.reviewed_by_id = user().id
        return save(document, 'partners', 'Document review saved.')

    @app.route('/workspace/control/partners/<int:provider_id>/review', methods=['POST'])
    @require('manage_marketplace')
    def control_partner_review(provider_id):
        partner = db.get_or_404(Provider, provider_id)
        action = request.form.get('action')
        if action not in ('APPROVED', 'UNDER_REVIEW', 'REJECTED'):
            abort(400)
        partner.status = action
        return save(partner, 'partners', 'Partner review saved.')

    @app.route('/workspace/control/website/<page>/draft', methods=['POST'])
    @require('manage_about')
    def control_website_draft(page):
        if page not in PAGES:
            abort(404)
        settings = get_site_settings()
        token = text('token', 128, True)
        if not public_config_token_matches(settings, token):
            abort(409, description='The published site changed. Reload before saving your draft.')
        cfg = get_public_config(settings)
        fields = set(name for names in CONTENT.values() for name in names) | {'site_title', 'meta_description'}
        values = {key: value for key, value in request.form.items() if key in fields}
        from cms_routes import MAX_TEXT_LENGTHS
        if any(len(value) > MAX_TEXT_LENGTHS.get(key, 20000) for key, value in values.items()):
            abort(400)
        home = cfg['home'].copy()
        if page == 'home' and 'home_structure' in request.form:
            if not allowed('manage_structure'):
                abort(403)
            order = request.form.getlist('order')
            if set(order) != set(['hero', 'about', 'tours', 'why', 'blog', 'contact']) or len(order) != 6:
                abort(400)
            home['order'] = order
            home['visibility'] = {key: key in request.form.getlist('visible') for key in order}
        revision = WebsiteRevision(page=page, payload_json=json.dumps(revision_payload(values, home, cfg)),
                                   base_token=token, author_id=user().id)
        db.session.add(revision)
        add_audit('drafted', 'website', page)
        db.session.commit()
        flash('Draft saved. The public website is unchanged.', 'success')
        return redirect(url_for('control_room', section='website', page=page))

    @app.post('/workspace/control/reviews/<int:review_id>')
    @require('manage_about')
    def control_review(review_id):
        from models import TravellerReview
        review = db.get_or_404(TravellerReview, review_id)
        action = request.form.get('action')
        if action == 'delete':
            db.session.delete(review)
        elif action in ('hide', 'show'):
            review.is_visible = action == 'show'
        else:
            abort(400)
        add_audit(action, 'traveller_review', review_id)
        from indexnow import notify_indexnow_cms_change
        notify_indexnow_cms_change('home', stage_only=True)
        db.session.commit()
        flash('Traveller review updated.', 'success')
        return redirect(url_for('control_room', section='website', page='reviews'))

    @app.route('/workspace/control/website/revisions/<int:revision_id>/publish', methods=['POST'])
    @require('manage_about')
    def control_website_publish(revision_id):
        revision = db.get_or_404(WebsiteRevision, revision_id)
        if revision.published_at or revision.is_backup:
            abort(409, description='Restore this saved revision as a new draft before publishing it.')
        settings = get_site_settings()
        payload = json.loads(revision.payload_json)
        cfg = get_public_config(settings)
        base = payload.get('_base')
        if base is None:
            conflict = not public_config_token_matches(settings, revision.base_token)
        else:
            conflict = any(cfg['content'].get(key, '') not in (original, payload['content'][key])
                           for key, original in base['content'].items())
            conflict = conflict or ('home' in base and cfg['home'] not in (base['home'], payload['home']))
        if conflict:
            abort(409, description='An edited field changed since this draft. Review those changes before publishing.')
        changes_home = base is None or 'home' in base
        if changes_home and payload.get('home') != cfg['home'] and not allowed('manage_structure'):
            abort(403)
        backup = WebsiteRevision(page=revision.page, payload_json=json.dumps({'content': cfg['content'], 'home': cfg['home']}),
                                 base_token=public_config_token(settings), author_id=user().id, is_backup=True)
        db.session.add(backup)
        apply_revision(cfg, payload)
        settings.public_config_json = json.dumps(cfg, ensure_ascii=False)
        revision.published_at = datetime.utcnow()
        add_audit('published', 'website', revision.page)
        from indexnow import notify_indexnow_cms_change
        notify_indexnow_cms_change(revision.page, stage_only=True)
        db.session.commit()
        flash('Website changes published.', 'success')
        return redirect(url_for('control_room', section='website', page=revision.page))

    @app.route('/workspace/control/website/revisions/<int:revision_id>/restore', methods=['POST'])
    @require('manage_about')
    def control_website_restore(revision_id):
        old = db.get_or_404(WebsiteRevision, revision_id)
        cfg = get_public_config(get_site_settings())
        payload = json.loads(old.payload_json)
        home = payload['home'] if '_base' not in payload or 'home' in payload['_base'] else cfg['home']
        revision = WebsiteRevision(page=old.page, payload_json=json.dumps(revision_payload(payload['content'], home, cfg)),
                                   base_token=public_config_token(get_site_settings()), author_id=user().id)
        db.session.add(revision)
        db.session.commit()
        flash('Revision restored as a draft. Review it before publishing.', 'success')
        return redirect(url_for('control_room', section='website', page=old.page))

    @app.route('/workspace/control/media/metadata/<int:asset_id>', methods=['POST'])
    @require('manage_media')
    def control_asset_metadata(asset_id):
        asset = db.get_or_404(MediaAsset, asset_id)
        if request.form.get('version', type=int) != asset.version:
            return jsonify(error='Image details changed. Reload before saving.'), 409
        # Location/category/tags share this asset's concurrency token too.
        asset.version += 1
        asset.title, asset.alt, asset.caption = text('title', 240, True), text('alt', 500), text('caption', 1000)
        db.session.flush([asset])
        metadata = db.session.get(AssetMetadata, asset_id) or AssetMetadata(asset_id=asset_id)
        metadata.location, metadata.category, metadata.tags = text('location', 240), text('category', 100), text('tags', 1000)
        db.session.add(metadata)
        add_audit('updated', 'media_asset', asset.id, 'Image metadata saved')
        db.session.commit()
        return jsonify(ok=True, version=asset.version)

    @app.route('/workspace/control/media/videos', methods=['GET', 'POST'])
    @require('manage_media')
    def control_videos():
        from cms_pages import media_page
        if request.method == 'GET':
            query=LibraryVideo.query
            live_path = get_site_settings().hero_animation_video
            if request.args.get('usage') == 'used':
                query = query.filter(LibraryVideo.path == live_path) if live_path else query.filter(False)
            elif request.args.get('usage') == 'unused' and live_path:
                query = query.filter(LibraryVideo.path != live_path)
            term=request.args.get('q','').strip()[:200]
            if term:
                query=query.filter(LibraryVideo.title.ilike(f'%{term}%'))
            order=LibraryVideo.created_at.asc() if request.args.get('sort')=='oldest' else LibraryVideo.created_at.desc()
            videos, pagination = media_page(query, (order, LibraryVideo.id.desc()))
            return jsonify(items=[dict(id=v.id, title=v.title, path=v.path, byte_size=v.byte_size, kind='video', usage=['Homepage opening film'] if live_path and v.path == live_path else [], created_at=v.created_at.isoformat())
                                  for v in videos], **(pagination or {}))
        from storage import save_video
        upload = request.files.get('file')
        if not upload or not upload.filename:
            abort(400)
        try:
            upload.stream.seek(0,2)
            byte_size=upload.stream.tell()
            upload.stream.seek(0)
            path = save_video(upload)
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        video = LibraryVideo(title=secure_filename(upload.filename)[:240], path=path, byte_size=byte_size)
        db.session.add(video)
        db.session.commit()
        return jsonify(id=video.id, title=video.title, path=video.path, kind='video'), 201

    @app.route('/workspace/control/media/videos/<int:video_id>/publish', methods=['POST'])
    @require('manage_media')
    def control_video_publish(video_id):
        video = db.get_or_404(LibraryVideo, video_id)
        settings = get_site_settings()
        settings.hero_animation_video = video.path
        add_audit('published', 'library_video', video.id)
        from indexnow import notify_indexnow_cms_change
        notify_indexnow_cms_change('home', stage_only=True)
        db.session.commit()
        return jsonify(ok=True)

    @app.route('/workspace/control/settings/notifications', methods=['POST'])
    @require('manage_users')
    def control_notifications():
        if user().role != 'owner':
            abort(403)
        preference = db.session.get(ControlPreference, 'notifications') or ControlPreference(key='notifications')
        preference.value_json = json.dumps({key: key in request.form for key in ('new_enquiries', 'trip_updates', 'partner_activities', 'system_alerts', 'marketing_updates')})
        db.session.add(preference)
        if 'delivery_preferences' in request.form:
            delivery = db.session.get(ControlPreference, 'delivery') or ControlPreference(key='delivery')
            values = {key: ('deliver_' + key) in request.form for key in ('email', 'messaging')}
            delivery.value_json = json.dumps(values)
            db.session.add(delivery)
            from models import NotificationOutbox
            disabled = [key for key, enabled in values.items() if not enabled]
            if disabled:
                db.session.execute(update(NotificationOutbox).where(
                    NotificationOutbox.channel.in_(disabled), NotificationOutbox.status.in_(['PENDING', 'FAILED'])
                ).values(status='CANCELLED', last_error='delivery disabled by owner', next_attempt_at=None))
        add_audit('updated', 'notification_preferences', user().id)
        db.session.commit()
        flash('Notification preferences saved for the organisation.', 'success')
        return redirect(url_for('control_room', section='settings'))

    @app.route('/workspace/control/invoices', methods=['POST'])
    @require('manage_users')
    def control_invoice_create():
        if user().role != 'owner':
            abort(403)
        invoice = Invoice(customer=text('customer', 200, True), description=text('description', 10000, True),
                          amount=money('amount'), due_date=day('due_date'))
        db.session.add(invoice)
        return save(invoice, 'settings', 'Invoice issued.')

    @app.route('/workspace/control/invoices/<int:invoice_id>', methods=['GET', 'POST'])
    @require('manage_users')
    def control_invoice(invoice_id):
        if user().role != 'owner':
            abort(403)
        invoice = db.get_or_404(Invoice, invoice_id)
        if request.method == 'POST':
            invoice.status = request.form.get('status')
            if invoice.status not in ('ISSUED', 'PAID', 'VOID'):
                abort(400)
            return save(invoice, 'settings', 'Invoice status updated.')
        return render_template('control_room/document.html', heading=f'Invoice RB-I-{invoice.id:05d}', customer=invoice.customer,
                               description=invoice.description, amount=invoice.amount, deadline=invoice.due_date, settings=get_site_settings())
