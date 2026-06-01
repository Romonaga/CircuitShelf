import numpy as np

from index_builder import IndexBuilder


class ImageStateService:
    def __init__(
        self,
        *,
        state,
        vector_store,
        image_store,
        chunker,
        embedder,
        config,
        trace_logger,
        embedding_model_name: str,
        effective_embedding_batch_size,
        update_index_detail,
        update_index_progress,
    ):
        self.state = state
        self.vector_store = vector_store
        self.image_store = image_store
        self.chunker = chunker
        self.embedder = embedder
        self.config = config
        self.trace_logger = trace_logger
        self.embedding_model_name = embedding_model_name
        self.effective_embedding_batch_size = effective_embedding_batch_size
        self.update_index_detail = update_index_detail
        self.update_index_progress = update_index_progress

    def load_db_image_state(self) -> int:
        image_data, captions, page_text, mime_types = self.image_store.load_state_payload()
        self.state.set_image_store(image_data)
        self.state.set_image_captions(captions)
        self.state.set_image_page_text(page_text)
        self.state.set_image_mime_types(mime_types)
        builder = IndexBuilder(
            self.state,
            self.chunker,
            self.embedder,
            self.config,
            self.trace_logger,
            batch_size_resolver=self.effective_embedding_batch_size,
        )
        return builder.build_image_index()

    def refresh_active_state_from_db(self) -> int:
        chunks, sources, metadata, embeddings = self.vector_store.load_state_payload()
        self.state.replace_catalog(
            chunks=chunks,
            sources=sources,
            metadata=metadata,
            embeddings=embeddings,
            image_store={},
            image_captions={},
            image_page_text={},
            image_mime_types={},
            image_id_list=[],
        )
        return self.load_db_image_state()

    def persist_db_image_state(self, file_records, target_state=None, rel_paths=None, progress_file=None) -> dict:
        target_state = target_state or self.state
        image_text = target_state.get_image_page_text()
        image_ids = target_state.get_image_id_list()
        image_payload = target_state.get_image_store()
        total_images = len(image_payload)
        if not progress_file:
            self.update_index_detail(
                savedImages=0,
                totalImagesToSave=total_images,
                skippedImages=0,
                indexedImageTexts=len(image_ids),
            )
        if progress_file:
            self.update_index_progress(
                current_file=progress_file,
                file_details={
                    "documentPhase": "Preparing image save",
                    "savedImages": 0,
                    "totalImagesToSave": total_images,
                    "skippedImages": 0,
                },
            )
        image_embeddings = {}
        if image_ids:
            if not progress_file:
                self.update_index_detail(imageEmbeddingTexts=0, imageEmbeddingTotal=len(image_ids))
            if progress_file:
                self.update_index_progress(
                    current_file=progress_file,
                    file_details={
                        "documentPhase": "Embedding image text",
                        "imageEmbeddingTexts": 0,
                        "imageEmbeddingTotal": len(image_ids),
                    },
                )
            encoded = self.embedder.encode(
                [image_text[key] for key in image_ids],
                batch_size=self.effective_embedding_batch_size(),
                convert_to_numpy=True,
            ).astype("float32")
            image_embeddings = {key: encoded[idx] for idx, key in enumerate(image_ids)}
            if not progress_file:
                self.update_index_detail(imageEmbeddingTexts=len(image_ids), imageEmbeddingTotal=len(image_ids))
            if progress_file:
                self.update_index_progress(
                    current_file=progress_file,
                    file_details={
                        "imageEmbeddingTexts": len(image_ids),
                        "imageEmbeddingTotal": len(image_ids),
                    },
                )

        def report_image_save_progress(saved_images, total_images, skipped_images=0, current_image=None):
            if progress_file:
                self.update_index_progress(
                    current_file=progress_file,
                    file_details={
                        "documentPhase": "Saving images",
                        "savedImages": saved_images,
                        "totalImagesToSave": total_images,
                        "skippedImages": skipped_images,
                        "currentImage": current_image,
                    },
                )
            else:
                self.update_index_detail(
                    savedImages=saved_images,
                    totalImagesToSave=total_images,
                    skippedImages=skipped_images,
                )

        payload = {
            "file_records": file_records,
            "image_store": image_payload,
            "image_captions": target_state.get_image_captions(),
            "image_page_text": target_state.get_image_page_text(),
            "image_embeddings": image_embeddings,
            "embedding_model": self.embedding_model_name,
            "metadata": target_state.get_metadata(),
            "progress_callback": report_image_save_progress,
        }
        if rel_paths is None:
            self.image_store.replace_catalog(**payload)
        else:
            self.image_store.upsert_sources(**payload, rel_paths=set(rel_paths))
        return {
            "storedImages": len(target_state.get_image_store()),
            "indexedImageTexts": len(image_ids),
            "ocrImageTexts": len(image_text),
        }

    def backfill_missing_image_embeddings(self, limit=512) -> int:
        missing = self.image_store.load_missing_embedding_inputs(limit=limit)
        if not missing:
            return 0
        self.trace_logger.info(f"🖼️ Backfilling {len(missing)} missing DB image embeddings.")
        encoded = self.embedder.encode(
            [row["embedding_text"] for row in missing],
            batch_size=self.effective_embedding_batch_size(),
            convert_to_numpy=True,
        ).astype("float32")
        self.image_store.update_embeddings(
            {row["image_key"]: encoded[idx] for idx, row in enumerate(missing)},
            self.embedding_model_name,
        )
        return len(missing)
