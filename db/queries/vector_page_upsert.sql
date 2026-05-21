INSERT INTO document_pages (
    document_id,
    page_number,
    extracted_text,
    text_char_count
)
VALUES (%s, %s, '', 0)
ON CONFLICT (document_id, page_number) DO UPDATE SET
    updated_at = now()
RETURNING id;
