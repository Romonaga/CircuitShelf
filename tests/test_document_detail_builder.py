from backend.services.document_detail_builder import DocumentDetailBuilder


class FakeState:
    def __init__(self):
        self.chunks = ["native page text", "ocr page text"]
        self.sources = ["/repo/training/4n35.pdf", "/repo/training/4n35.pdf"]
        self.metadata = [
            {"source": "/repo/training/4n35.pdf", "parent_source": "/repo/training/4n35.pdf", "page": 2, "section": "Description"},
            {
                "source": "/repo/training/4n35.pdf",
                "parent_source": "/repo/training/4n35.pdf",
                "page": 2,
                "section": "Image OCR",
                "chunk_type": "ocr",
                "source_image_id": "4n35.pdf_page2_img1",
            },
        ]

    def get_chunks(self):
        return self.chunks

    def get_metadata(self):
        return self.metadata

    def get_sources(self):
        return self.sources

    def get_image_store(self):
        return {"4n35.pdf_page2_img1": "base64"}

    def get_image_captions(self):
        return {"4n35.pdf_page2_img1": "Pinout image"}

    def get_image_page_text(self):
        return {"4n35.pdf_page2_img1": "pin 1 anode pin 2 cathode"}

    def get_image_mime_types(self):
        return {"4n35.pdf_page2_img1": "image/png"}


class FakeVectorStore:
    training_dir = "/repo/training"

    def rel_path_for_source(self, source, meta=None):
        source = str(source)
        prefix = f"{self.training_dir}/"
        return source[len(prefix):] if source.startswith(prefix) else source

    def list_document_stats(self):
        return [
            {
                "source_path": "4n35.pdf",
                "raw_chunk_count": 2,
                "actual_chunk_count": 2,
                "chunk_count": 2,
                "dropped_chunk_count": 0,
                "extracted_image_count": 1,
                "stored_image_count": 1,
                "indexed_image_text_count": 1,
                "ocr_image_text_count": 1,
            }
        ]


def test_document_detail_matches_full_path_state_sources_to_relative_document_name():
    builder = DocumentDetailBuilder(
        state=FakeState(),
        vector_store=FakeVectorStore(),
        image_asset_belongs_to_document=lambda image_id, doc: image_id.startswith(f"{doc}_page"),
        extract_page_number=lambda image_id: 2 if "_page2_" in image_id else None,
        document_source_from_metadata=lambda source, metadata: metadata.get("parent_source") or source,
        source_image_id_from_metadata=lambda source, metadata: metadata.get("source_image_id"),
        extract_pinout_map=lambda chunks, metadata, doc_name: {"pins": []},
        get_or_build_datasheet_intelligence=lambda doc_name, chunks, metadata: {"facts": [], "pinout": {"pins": []}},
        display_source_name=lambda source: source,
    )

    detail = builder.build("4n35.pdf")

    assert len(detail["chunks"]) == 2
    assert detail["pages"][0]["page"] == 2
    assert [chunk["preview"] for chunk in detail["pages"][0]["chunks"]] == ["native page text", "ocr page text"]
    assert detail["pages"][0]["images"][0]["ocrText"] == "pin 1 anode pin 2 cathode"
