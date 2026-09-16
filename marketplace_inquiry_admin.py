"""Workspace inbox for independent RI BUROM marketplace enquiries."""

from flask import abort, flash, redirect, render_template, request, url_for
from sqlalchemy import func, or_

from app import add_audit
from marketplace_models import INQUIRY_STATUSES, MarketplaceInquiry, Provider, Service
from models import AuditLog, db


_STATUS_ORDER = ['NEW', 'CONTACTED', 'IN_PROGRESS', 'QUOTED', 'CONFIRMED', 'DECLINED', 'CLOSED']


def _status_filter(value):
    value = (value or '').strip().upper()
    return value if value in INQUIRY_STATUSES else ''


def register_marketplace_inquiry_admin(flask_app, view_required, manage_required):
    if getattr(flask_app, '_ri_burom_marketplace_inquiry_admin_registered', False):
        return

    flask_app._ri_burom_marketplace_inquiry_admin_registered = True

    @flask_app.route('/workspace/marketplace/inquiries')
    @view_required
    def workspace_marketplace_inquiries():
        status = _status_filter(request.args.get('status'))
        provider_id = request.args.get('provider_id', type=int)
        service_id = request.args.get('service_id', type=int)
        query = (request.args.get('q') or '').strip()

        inquiry_query = MarketplaceInquiry.query
        if status:
            inquiry_query = inquiry_query.filter(MarketplaceInquiry.status == status)
        if provider_id:
            inquiry_query = inquiry_query.filter(MarketplaceInquiry.provider_id == provider_id)
        if query:
            pattern = f'%{query}%'
            inquiry_query = inquiry_query.filter(or_(
                MarketplaceInquiry.name.ilike(pattern),
                MarketplaceInquiry.email.ilike(pattern),
                MarketplaceInquiry.phone.ilike(pattern),
                MarketplaceInquiry.provider_name.ilike(pattern),
                MarketplaceInquiry.service_name.ilike(pattern),
                MarketplaceInquiry.selected_services_json.ilike(pattern),
                MarketplaceInquiry.category_name.ilike(pattern),
                MarketplaceInquiry.requirements.ilike(pattern),
            ))

        page = max(request.args.get('page', default=1, type=int) or 1, 1)
        per_page = 50
        ordered_query = inquiry_query.order_by(
            MarketplaceInquiry.created_at.desc(),
            MarketplaceInquiry.id.desc(),
        )

        if service_id:
            # selected_services_json is retained for backward compatibility.
            # Filtering this legacy denormalized field still needs application
            # filtering, but only this less-common filter takes that path.
            matched = [
                inquiry
                for inquiry in ordered_query.all()
                if service_id in inquiry.selected_service_ids
            ]
            total = len(matched)
            total_pages = max(1, (total + per_page - 1) // per_page)
            page = min(page, total_pages)
            start = (page - 1) * per_page
            inquiries = matched[start:start + per_page]
        else:
            total = inquiry_query.count()
            total_pages = max(1, (total + per_page - 1) // per_page)
            page = min(page, total_pages)
            inquiries = (
                ordered_query
                .offset((page - 1) * per_page)
                .limit(per_page)
                .all()
            )

        count_rows = (
            db.session.query(MarketplaceInquiry.status, func.count(MarketplaceInquiry.id))
            .group_by(MarketplaceInquiry.status)
            .all()
        )
        count_map = dict(count_rows)
        counts = {item_status: count_map.get(item_status, 0) for item_status in _STATUS_ORDER}
        return render_template(
            'marketplace_inquiries.html',
            inquiries=inquiries,
            providers=Provider.query.order_by(Provider.name.asc()).all(),
            services=Service.query.order_by(Service.name.asc()).all(),
            statuses=_STATUS_ORDER,
            counts=counts,
            current_status=status,
            current_provider_id=provider_id,
            current_service_id=service_id,
            current_query=query,
            total=total,
            page=page,
            total_pages=total_pages,
        )

    @flask_app.route('/workspace/marketplace/inquiries/<int:id>')
    @view_required
    def workspace_marketplace_inquiry_detail(id):
        inquiry = db.session.get(MarketplaceInquiry, id)
        if inquiry is None:
            abort(404)

        audits = AuditLog.query.filter(
            AuditLog.target_type.in_(['marketplace_inquiry', 'marketplace_inquiries']),
            AuditLog.target_id == str(inquiry.id),
        ).order_by(AuditLog.id.desc()).limit(50).all()

        return render_template(
            'marketplace_inquiry_detail.html',
            inquiry=inquiry,
            audits=audits,
            statuses=_STATUS_ORDER,
        )

    @flask_app.route('/workspace/marketplace/inquiries/<int:id>/status', methods=['POST'])
    @manage_required
    def marketplace_inquiry_status_update(id):
        inquiry = db.session.get(MarketplaceInquiry, id)
        if inquiry is None:
            abort(404)

        old_status = inquiry.status
        new_status = _status_filter(request.form.get('status'))
        if not new_status:
            flash('Please select a valid enquiry status.', 'error')
            return redirect(url_for('workspace_marketplace_inquiry_detail', id=id))

        if old_status == new_status:
            flash('Enquiry status is unchanged.', 'info')
            return redirect(url_for('workspace_marketplace_inquiry_detail', id=id))

        inquiry.status = new_status
        add_audit(
            'status_changed',
            'marketplace_inquiry',
            inquiry.id,
            f'{old_status} -> {new_status}; provider={inquiry.provider_name}; service={inquiry.service_name}',
        )
        db.session.commit()

        flash(f'Enquiry #{inquiry.id} moved from {old_status} to {new_status}.', 'success')
        return redirect(url_for('workspace_marketplace_inquiry_detail', id=id))
