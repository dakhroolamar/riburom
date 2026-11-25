-- Run on RI BUROM's production neondb as its owner. CREATE ROLE deliberately
-- fails on a name collision. Set its password separately with psql \password
-- over a verified TLS connection or the provider's password manager.
BEGIN;
CREATE ROLE riburom_worker_app LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE riburom_worker_app IN DATABASE neondb SET search_path = public;
GRANT CONNECT ON DATABASE neondb TO riburom_worker_app;
GRANT USAGE ON SCHEMA public TO riburom_worker_app;
GRANT SELECT ON public.alembic_version TO riburom_worker_app;
GRANT SELECT, INSERT ON public.audit_logs TO riburom_worker_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON
    public.about_content, public.about_sections, public.cms_media_assets,
    public.cms_media_collection_items, public.cms_media_collections, public.cms_page_sections,
    public.control_asset_metadata, public.control_invoices, public.control_leads,
    public.control_library_videos, public.control_partner_documents, public.control_partner_operations,
    public.control_preferences, public.control_quotes, public.control_service_inventory,
    public.control_trip_updates, public.control_trips, public.control_website_revisions,
    public.marketplace_inquiries, public.messages, public.notification_outbox, public.package_items,
    public.packages, public.provider_type_assignments, public.provider_types, public.providers,
    public.review_attachments, public.service_categories, public.service_images, public.services,
    public.site_settings, public.team_members, public.traveller_reviews, public.users
TO riburom_worker_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO riburom_worker_app;
COMMIT;
