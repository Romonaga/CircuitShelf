SELECT p.pack_key,
       p.display_name AS pack_display_name,
       p.root_path,
       p.summary AS pack_summary,
       p.board AS pack_board,
       p.framework AS pack_framework,
       p.languages AS pack_languages,
       p.libraries AS pack_libraries,
       p.components AS pack_components,
       p.interfaces AS pack_interfaces,
       f.relative_path,
       f.language,
       f.role,
       f.board,
       f.framework,
       f.libraries,
       f.components,
       f.interfaces,
       f.pins,
       f.updated_at
FROM code_sample_files f
JOIN code_sample_packs p ON p.id = f.pack_id
JOIN documents d ON d.id = f.document_id
WHERE d.source_path = %s;
