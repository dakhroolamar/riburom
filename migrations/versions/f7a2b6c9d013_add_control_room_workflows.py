"""Add persistent Control Room workflows without altering customer records."""
from alembic import op
import sqlalchemy as sa
revision = 'f7a2b6c9d013'
down_revision = 'e6f7a8b9c012'
branch_labels = None
depends_on = None

def upgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if 'control_leads' not in existing:
        op.create_table('control_leads',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('source', sa.String(length=20), nullable=False),
            sa.Column('source_id', sa.Integer(), nullable=False),
            sa.Column('status', sa.String(length=24), nullable=False),
            sa.Column('assigned_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('notes', sa.Text(), nullable=False),
            sa.Column('budget', sa.Numeric(precision=12, scale=2), nullable=True),
            sa.Column('call_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.UniqueConstraint('source', 'source_id', name='uq_control_lead_source'))
    if 'control_trips' not in existing:
        op.create_table('control_trips',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('lead_id', sa.Integer(), sa.ForeignKey('control_leads.id'), nullable=True, unique=True),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('destination', sa.String(length=300), nullable=False),
            sa.Column('start_date', sa.Date(), nullable=False),
            sa.Column('end_date', sa.Date(), nullable=False),
            sa.Column('travellers', sa.Integer(), nullable=False),
            sa.Column('status', sa.String(length=24), nullable=False),
            sa.Column('guide', sa.String(length=200), nullable=False),
            sa.Column('driver', sa.String(length=200), nullable=False),
            sa.Column('vehicle', sa.String(length=200), nullable=False),
            sa.Column('itinerary_json', sa.Text(), nullable=False),
            sa.Column('accommodation_json', sa.Text(), nullable=False),
            sa.Column('checklist_json', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False))
        op.create_index('ix_control_trips_start_date', 'control_trips', ['start_date'], unique=False)
        op.create_index('ix_control_trips_status', 'control_trips', ['status'], unique=False)
    if 'control_trip_updates' not in existing:
        op.create_table('control_trip_updates',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('trip_id', sa.Integer(), sa.ForeignKey('control_trips.id'), nullable=False),
            sa.Column('author_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('message', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False))
        op.create_index('ix_control_trip_updates_trip_id', 'control_trip_updates', ['trip_id'], unique=False)
    if 'control_quotes' not in existing:
        op.create_table('control_quotes',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('lead_id', sa.Integer(), sa.ForeignKey('control_leads.id'), nullable=False),
            sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column('summary', sa.Text(), nullable=False),
            sa.Column('valid_until', sa.Date(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False))
        op.create_index('ix_control_quotes_lead_id', 'control_quotes', ['lead_id'], unique=False)
    if 'control_partner_documents' not in existing:
        op.create_table('control_partner_documents',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('provider_id', sa.Integer(), sa.ForeignKey('providers.id'), nullable=False),
            sa.Column('kind', sa.String(length=80), nullable=False),
            sa.Column('file_name', sa.String(length=240), nullable=False),
            sa.Column('file_data', sa.LargeBinary(), nullable=False),
            sa.Column('status', sa.String(length=24), nullable=False),
            sa.Column('review_note', sa.Text(), nullable=False),
            sa.Column('expires_on', sa.Date(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('reviewed_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
        op.create_index('ix_control_partner_documents_provider_id', 'control_partner_documents', ['provider_id'], unique=False)
    if 'control_website_revisions' not in existing:
        op.create_table('control_website_revisions',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('page', sa.String(length=80), nullable=False),
            sa.Column('payload_json', sa.Text(), nullable=False),
            sa.Column('base_token', sa.String(length=128), nullable=False),
            sa.Column('author_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('published_at', sa.DateTime(), nullable=True))
        op.create_index('ix_control_website_revisions_page', 'control_website_revisions', ['page'], unique=False)
    if 'control_preferences' not in existing:
        op.create_table('control_preferences',
            sa.Column('key', sa.String(length=80), nullable=False, primary_key=True),
            sa.Column('value_json', sa.Text(), nullable=False))
    if 'control_invoices' not in existing:
        op.create_table('control_invoices',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('customer', sa.String(length=200), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column('due_date', sa.Date(), nullable=False),
            sa.Column('status', sa.String(length=24), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False))
    if 'control_asset_metadata' not in existing:
        op.create_table('control_asset_metadata',
            sa.Column('asset_id', sa.Integer(), sa.ForeignKey('cms_media_assets.id'), nullable=False, primary_key=True),
            sa.Column('location', sa.String(length=240), nullable=False),
            sa.Column('category', sa.String(length=100), nullable=False),
            sa.Column('tags', sa.String(length=1000), nullable=False))
    if 'control_library_videos' not in existing:
        op.create_table('control_library_videos',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('title', sa.String(length=240), nullable=False),
            sa.Column('path', sa.String(length=1000), nullable=False),
            sa.Column('byte_size', sa.Integer(), nullable=False),
            sa.Column('caption', sa.String(length=1000), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False))
    if 'control_service_inventory' not in existing:
        op.create_table('control_service_inventory',
            sa.Column('service_id', sa.Integer(), sa.ForeignKey('services.id'), primary_key=True, nullable=False),
            sa.Column('location', sa.String(240), nullable=False),
            sa.Column('price', sa.Numeric(12, 2)),
            sa.Column('available_slots', sa.Integer()))

def downgrade():
    op.drop_table('control_service_inventory')
    op.drop_table('control_library_videos')
    op.drop_table('control_asset_metadata')
    op.drop_table('control_invoices')
    op.drop_table('control_preferences')
    op.drop_table('control_website_revisions')
    op.drop_table('control_partner_documents')
    op.drop_table('control_quotes')
    op.drop_table('control_trip_updates')
    op.drop_table('control_trips')
    op.drop_table('control_leads')
