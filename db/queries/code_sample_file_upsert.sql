WITH pack AS (
    INSERT INTO code_sample_packs (
        pack_key,
        display_name,
        root_path,
        summary,
        board,
        framework,
        languages,
        libraries,
        components,
        interfaces,
        updated_at
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s::text[], %s::text[], %s::text[], %s::text[], now())
    ON CONFLICT (pack_key) DO UPDATE SET
        display_name = EXCLUDED.display_name,
        root_path = EXCLUDED.root_path,
        summary = EXCLUDED.summary,
        board = COALESCE(NULLIF(EXCLUDED.board, ''), code_sample_packs.board),
        framework = COALESCE(NULLIF(EXCLUDED.framework, ''), code_sample_packs.framework),
        languages = (
            SELECT ARRAY(
                SELECT DISTINCT item
                FROM unnest(code_sample_packs.languages || EXCLUDED.languages) AS item
                WHERE item <> ''
                ORDER BY item
            )
        ),
        libraries = (
            SELECT ARRAY(
                SELECT DISTINCT item
                FROM unnest(code_sample_packs.libraries || EXCLUDED.libraries) AS item
                WHERE item <> ''
                ORDER BY item
            )
        ),
        components = (
            SELECT ARRAY(
                SELECT DISTINCT item
                FROM unnest(code_sample_packs.components || EXCLUDED.components) AS item
                WHERE item <> ''
                ORDER BY item
            )
        ),
        interfaces = (
            SELECT ARRAY(
                SELECT DISTINCT item
                FROM unnest(code_sample_packs.interfaces || EXCLUDED.interfaces) AS item
                WHERE item <> ''
                ORDER BY item
            )
        ),
        updated_at = now()
    RETURNING id
)
INSERT INTO code_sample_files (
    pack_id,
    document_id,
    relative_path,
    language,
    role,
    board,
    framework,
    libraries,
    components,
    interfaces,
    pins,
    updated_at
)
SELECT
    pack.id,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s::text[],
    %s::text[],
    %s::text[],
    %s::jsonb,
    now()
FROM pack
ON CONFLICT (document_id) DO UPDATE SET
    pack_id = EXCLUDED.pack_id,
    relative_path = EXCLUDED.relative_path,
    language = EXCLUDED.language,
    role = EXCLUDED.role,
    board = EXCLUDED.board,
    framework = EXCLUDED.framework,
    libraries = EXCLUDED.libraries,
    components = EXCLUDED.components,
    interfaces = EXCLUDED.interfaces,
    pins = EXCLUDED.pins,
    updated_at = now()
RETURNING id;
