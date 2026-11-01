-- Organization-specific settings. Apply manually after migration 004.
-- This migration does not modify legacy Platform Administration settings.
CREATE TABLE IF NOT EXISTS organization_settings (
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    setting_key VARCHAR(80) NOT NULL,
    setting_value VARCHAR(500) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (organization_id, setting_key)
);
