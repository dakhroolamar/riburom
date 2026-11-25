-- Run once as the owner of RI BUROM's production database. Existing roles or
-- schemas cause the transaction to abort. Set a unique login password separately.
BEGIN;
CREATE ROLE riburom_comparison_reader LOGIN NOINHERIT;
CREATE SCHEMA riburom_public_comparison;
ALTER ROLE riburom_comparison_reader SET search_path = pg_catalog, riburom_public_comparison;
ALTER ROLE riburom_comparison_reader SET default_transaction_read_only = on;

-- Views use the owner to read the source tables. The login gets no base-table
-- grants. Keep unpublished reviews, media, tours and providers out of its scope.
SET LOCAL search_path = riburom_public_comparison, pg_catalog;
CREATE VIEW packages AS SELECT * FROM public.packages WHERE published;
CREATE VIEW providers AS SELECT * FROM public.providers
    WHERE is_active AND status IN ('APPROVED', 'PUBLISHED', 'ACTIVE');
CREATE VIEW services AS SELECT s.* FROM public.services s JOIN providers p ON p.id = s.provider_id
    WHERE s.is_active AND s.status IN ('PUBLISHED', 'ACTIVE');
CREATE VIEW service_images AS SELECT i.* FROM public.service_images i JOIN services s ON s.id = i.service_id;
CREATE VIEW service_categories AS SELECT c.* FROM public.service_categories c
    WHERE EXISTS (SELECT 1 FROM services s WHERE s.category_id = c.id);
CREATE VIEW provider_type_assignments AS SELECT a.* FROM public.provider_type_assignments a
    JOIN providers p ON p.id = a.provider_id;
CREATE VIEW provider_types AS SELECT t.* FROM public.provider_types t
    WHERE EXISTS (SELECT 1 FROM provider_type_assignments a WHERE a.provider_type_id = t.id);
CREATE VIEW traveller_reviews AS SELECT * FROM public.traveller_reviews WHERE is_visible AND status = 'published';
CREATE VIEW review_attachments AS SELECT a.* FROM public.review_attachments a
    JOIN traveller_reviews r ON r.id = a.review_id;
CREATE VIEW cms_media_collections AS SELECT c.* FROM public.cms_media_collections c
    WHERE c.key IN ('hero','footer_partners','home_gallery','home_about_gallery')
       OR EXISTS (SELECT 1 FROM packages p WHERE c.key = 'tour-' || p.id::text);
CREATE VIEW cms_media_collection_items AS SELECT i.* FROM public.cms_media_collection_items i
    JOIN cms_media_collections c ON c.id = i.collection_id WHERE i.visible;
CREATE VIEW cms_media_assets AS SELECT a.* FROM public.cms_media_assets a
    WHERE EXISTS (SELECT 1 FROM cms_media_collection_items i WHERE i.asset_id = a.id);
CREATE VIEW site_settings AS SELECT * FROM public.site_settings WHERE id = 1;
CREATE VIEW about_content AS SELECT * FROM public.about_content WHERE id = 1;
CREATE VIEW about_sections AS SELECT * FROM public.about_sections WHERE enabled;
CREATE VIEW team_members AS SELECT * FROM public.team_members;
CREATE VIEW cms_page_sections AS SELECT * FROM public.cms_page_sections WHERE page = 'home' AND key = 'hero';

GRANT USAGE ON SCHEMA riburom_public_comparison TO riburom_comparison_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA riburom_public_comparison TO riburom_comparison_reader;
COMMIT;
