BEGIN;

CREATE TABLE IF NOT EXISTS ai_model_pricing_variants (
    id bigserial PRIMARY KEY,
    provider_type_id smallint NOT NULL REFERENCES ai_provider_types(id) ON DELETE CASCADE,
    model_name text NOT NULL,
    context_band text NOT NULL DEFAULT 'short',
    service_tier text NOT NULL DEFAULT 'standard',
    input_per_million numeric(12, 6) NOT NULL CHECK (input_per_million >= 0),
    cached_input_per_million numeric(12, 6) NOT NULL CHECK (cached_input_per_million >= 0),
    output_per_million numeric(12, 6) NOT NULL CHECK (output_per_million >= 0),
    currency text NOT NULL DEFAULT 'USD',
    source_note text NOT NULL DEFAULT '',
    is_active boolean NOT NULL DEFAULT true,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (provider_type_id, model_name, context_band, service_tier)
);

CREATE INDEX IF NOT EXISTS ai_model_pricing_variants_lookup_idx
    ON ai_model_pricing_variants (provider_type_id, model_name, context_band, service_tier)
    WHERE is_active = true;

INSERT INTO ai_model_pricing_variants (
    provider_type_id,
    model_name,
    context_band,
    service_tier,
    input_per_million,
    cached_input_per_million,
    output_per_million,
    source_note
)
SELECT p.id,
       v.model_name,
       v.context_band,
       v.service_tier,
       v.input_rate,
       v.cached_rate,
       v.output_rate,
       'OpenAI API pricing page, standard context under 270K unless context_band = long.'
FROM ai_provider_types p
CROSS JOIN (
    VALUES
        ('gpt-5.5', 'short', 'standard', 5.000000, 0.500000, 30.000000),
        ('gpt-5.5', 'long', 'standard', 10.000000, 1.000000, 45.000000),
        ('gpt-5.5-pro', 'short', 'standard', 30.000000, 0.000000, 180.000000),
        ('gpt-5.5-pro', 'long', 'standard', 60.000000, 0.000000, 270.000000),
        ('gpt-5.4', 'short', 'standard', 2.500000, 0.250000, 15.000000),
        ('gpt-5.4', 'long', 'standard', 5.000000, 0.500000, 22.500000),
        ('gpt-5.4-mini', 'short', 'standard', 0.750000, 0.075000, 4.500000),
        ('gpt-5.4-nano', 'short', 'standard', 0.200000, 0.020000, 1.250000),
        ('gpt-5.4-pro', 'short', 'standard', 30.000000, 0.000000, 180.000000),
        ('gpt-5.4-pro', 'long', 'standard', 60.000000, 0.000000, 270.000000),
        ('gpt-5.5', 'short', 'batch_flex', 2.500000, 0.250000, 15.000000),
        ('gpt-5.5', 'long', 'batch_flex', 5.000000, 0.500000, 22.500000),
        ('gpt-5.5-pro', 'short', 'batch_flex', 15.000000, 0.000000, 90.000000),
        ('gpt-5.5-pro', 'long', 'batch_flex', 30.000000, 0.000000, 135.000000),
        ('gpt-5.4', 'short', 'batch_flex', 1.250000, 0.125000, 7.500000),
        ('gpt-5.4', 'long', 'batch_flex', 2.500000, 0.250000, 11.250000),
        ('gpt-5.4-mini', 'short', 'batch_flex', 0.375000, 0.037500, 2.250000),
        ('gpt-5.4-nano', 'short', 'batch_flex', 0.100000, 0.010000, 0.625000),
        ('gpt-5.4-pro', 'short', 'batch_flex', 15.000000, 0.000000, 90.000000),
        ('gpt-5.4-pro', 'long', 'batch_flex', 30.000000, 0.000000, 135.000000),
        ('gpt-5.5', 'short', 'priority', 12.500000, 1.250000, 75.000000),
        ('gpt-5.4', 'short', 'priority', 5.000000, 0.500000, 30.000000),
        ('gpt-5.4-mini', 'short', 'priority', 1.500000, 0.150000, 9.000000)
) AS v(model_name, context_band, service_tier, input_rate, cached_rate, output_rate)
WHERE p.code = 'openai'
ON CONFLICT (provider_type_id, model_name, context_band, service_tier) DO UPDATE SET
    input_per_million = EXCLUDED.input_per_million,
    cached_input_per_million = EXCLUDED.cached_input_per_million,
    output_per_million = EXCLUDED.output_per_million,
    currency = EXCLUDED.currency,
    source_note = EXCLUDED.source_note,
    is_active = true,
    updated_at = now();

INSERT INTO schema_migrations (version, name)
VALUES (23, 'ai_pricing_variants')
ON CONFLICT (version) DO NOTHING;

COMMIT;
