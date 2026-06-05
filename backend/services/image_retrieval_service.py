import re


class ImageRetrievalService:
    def __init__(self, *, state, embedder, image_store):
        self.state = state
        self.embedder = embedder
        self.image_store = image_store

    def search_top_images(self, question: str, top_n: int = 4, *, entity_id: int | None = None) -> list[tuple[str, float]]:
        action_keywords = ["click", "enter", "select", "choose", "screen", "dashboard", "button", "setting"]
        query_emb = self.embedder.encode(
            [question],
            convert_to_numpy=True,
            normalize_embeddings=True,
        ).astype("float32")
        results = []

        for row in self.image_store.search_images(query_emb[0], top_k=top_n * 2, entity_id=entity_id):
            img_id = row["image_key"]
            score_boost = 0.0
            ocr_text = str(row.get("ocr_text") or "").lower()
            if any(kw in ocr_text for kw in action_keywords):
                score_boost += 0.05
            results.append((img_id, float(row["distance"]) - score_boost))

        return sorted(results, key=lambda x: x[1])[:top_n]

    @staticmethod
    def extract_doc_and_page(img_id: str) -> tuple[str, int]:
        match = re.search(r"(.+?)_page(\d+)_(?:img\d+|render)$", img_id)
        if match:
            doc_name, page_str = match.groups()
            return doc_name, int(page_str)
        return img_id, -1

    def build_image_markdown_blocks(
        self,
        question: str,
        selected_chunks: list[dict] | None = None,
        *,
        entity_id: int | None = None,
    ) -> list[str]:
        linked_images = []
        seen_images = set()
        for chunk in selected_chunks or []:
            image_id = chunk.get("source_image_id")
            if image_id and image_id not in seen_images:
                linked_images.append((image_id, -1.0))
                seen_images.add(image_id)

        matched_images = linked_images
        for img_id, score in self.search_top_images(question, top_n=10, entity_id=entity_id):
            if img_id in seen_images:
                continue
            matched_images.append((img_id, score))
            seen_images.add(img_id)
            if len(matched_images) >= 10:
                break

        image_entries = []
        for img_id, _ in matched_images:
            doc_name, page = self.extract_doc_and_page(img_id)
            image_entries.append((doc_name, page, img_id))

        image_entries.sort(key=lambda x: (x[0], x[1]))

        blocks = []
        current_doc = None
        image_blocks = []

        for doc_name, page, img_id in image_entries:
            if doc_name != current_doc:
                if current_doc is not None:
                    blocks.append(f"""
<details style="margin-bottom: 1em;">
<summary>📄 {current_doc}</summary>
{''.join(image_blocks)}
</details>
""")
                current_doc = doc_name
                image_blocks = []

            img_data = self.state.image_store.get(img_id)
            mime_type = self.state.image_mime_types.get(img_id, "image/png")
            ocr_text = self.state.image_page_text.get(img_id, "")
            if not img_data:
                continue

            clean_ocr = ocr_text.strip().replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if len(clean_ocr) > 1500:
                clean_ocr = clean_ocr[:1500] + "..."
            caption = self.state.image_captions.get(img_id, img_id)

            image_blocks.append(f"""
<div style="margin-left: 1em;">
<details style="margin-bottom: 1em;">
<summary>📷 {caption}</summary>

<p><img src="data:{mime_type};base64,{img_data}" alt="{img_id}" style="max-width: 100%; height: auto;" /></p>

<div style="margin-left: 1.0em;">
<details>
<summary>🔍 View OCR Text</summary> 
<pre><code>{clean_ocr}</code></pre>
</details>
</div>

</details>
</div>
""")

        if current_doc is not None:
            blocks.append(f"""
<details style="margin-bottom: 1em;">
<summary>📄 {current_doc}</summary>
{''.join(image_blocks)}
</details>
""")

        return blocks
