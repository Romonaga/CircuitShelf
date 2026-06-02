import base64
import os
import re
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO

import fitz
from docx import Document
from lxml import etree
from PIL import Image

from ocr_utils import should_skip_image_dimensions

PDF_NATIVE_LOCK = threading.Lock()


class DocumentProcessingService:
    def __init__(
        self,
        *,
        config,
        trace_logger,
        state,
        chunker,
        token_utils,
        run_ocr,
        render_pdf_visual_pages,
        link_chunks_to_rendered_pages,
        detected_cpu_count,
        reserved_core_count,
        usable_core_count,
        document_worker_count,
        ocr_worker_count,
        current_document_workers,
        begin_document_worker,
        finish_document_worker,
        pdf_ext: str,
    ):
        self.config = config
        self.trace_logger = trace_logger
        self.state = state
        self.chunker = chunker
        self.token_utils = token_utils
        self.run_ocr = run_ocr
        self.render_pdf_visual_pages = render_pdf_visual_pages
        self.link_chunks_to_rendered_pages = link_chunks_to_rendered_pages
        self.detected_cpu_count = detected_cpu_count
        self.reserved_core_count = reserved_core_count
        self.usable_core_count = usable_core_count
        self.document_worker_count = document_worker_count
        self.ocr_worker_count = ocr_worker_count
        self.current_document_workers = current_document_workers
        self.begin_document_worker = begin_document_worker
        self.finish_document_worker = finish_document_worker
        self.pdf_ext = pdf_ext

    def ocr_image_bytes(self, image_bytes, image_id):
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        result = self.run_ocr(image, self.config)
        if result.skipped:
            return {
                "accepted": False,
                "text": "",
                "score": 0.0,
                "reason": result.skip_reason,
                "confidence": result.confidence,
                "skipped": True,
            }

        cleaned_text = self.chunker.clean_ocr_text(result.text)
        score, reason = self.chunker.evaluate_ocr_quality(cleaned_text, result.confidence)
        accepted = score >= self.config.get("OCR_TXT_DROP_SCORE", 0.4)
        return {
            "accepted": accepted,
            "text": cleaned_text,
            "score": score,
            "reason": reason,
            "confidence": result.confidence,
            "skipped": False,
        }

    @staticmethod
    def format_confidence(confidence):
        return f", confidence: {confidence:.1f}" if confidence is not None else ""

    def image_bytes_to_png_bytes(self, image_bytes, image_id="image"):
        try:
            with Image.open(BytesIO(image_bytes)) as image:
                if image.mode not in ("RGB", "RGBA"):
                    image = image.convert("RGBA" if "transparency" in image.info else "RGB")
                output = BytesIO()
                image.save(output, format="PNG")
                return output.getvalue()
        except Exception as exc:
            self.trace_logger.warning(f"⚠️ Could not normalize {image_id} to PNG for web display: {exc}")
            return image_bytes

    def get_ocr_worker_count(self, item_count):
        if not self.config.get("USE_MULTITHREAD_OCR", False) or item_count <= 1:
            return 1
        return self.ocr_worker_count(
            item_count,
            active_document_workers=self.current_document_workers(),
            cpu_count=self.detected_cpu_count(),
        )

    def ocr_pdf_image_job(self, job):
        order, page_num, img_index, image_bytes, img_name = job
        ocr_result = self.ocr_image_bytes(image_bytes, img_name)
        web_image_bytes = self.image_bytes_to_png_bytes(image_bytes, img_name)
        return {
            "order": order,
            "page_num": page_num,
            "img_index": img_index,
            "image_bytes": image_bytes,
            "img_name": img_name,
            "ocr_result": ocr_result,
            "web_image_bytes": web_image_bytes,
        }

    def run_pdf_image_ocr_jobs(self, image_jobs):
        if not image_jobs:
            return []

        worker_count = self.get_ocr_worker_count(len(image_jobs))
        if worker_count == 1:
            return [self.ocr_pdf_image_job(job) for job in image_jobs]

        self.trace_logger.info(
            f"🧵 OCR processing {len(image_jobs)} PDF images with {worker_count} workers "
            f"({self.detected_cpu_count()} cores, reserving {self.reserved_core_count()} cores, "
            f"{self.current_document_workers()} active document workers)"
        )
        results = []
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {executor.submit(self.ocr_pdf_image_job, job): job for job in image_jobs}
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as exc:
                    job = futures[future]
                    self.trace_logger.warning(f"❌ OCR worker failed for {job[4]}: {exc}")

        results.sort(key=lambda item: item["order"])
        return results

    @staticmethod
    def should_report_page_progress(page_number, total_pages, last_reported, min_interval=10):
        if page_number <= 1 or page_number >= total_pages:
            return True
        return page_number - last_reported >= min_interval

    @staticmethod
    def rendered_page_source_text(rendered_page):
        text = (rendered_page.searchable_text or "").strip()
        caption = (rendered_page.caption or "").strip()
        if caption and text.startswith(caption):
            return text[len(caption):].strip()
        return text

    def add_pdf_rendered_pages(
        self,
        path,
        target_state,
        progress_callback=None,
        extra_chunks=None,
        extra_sources=None,
        extra_meta=None,
    ):
        if not self.config.get("PDF_RENDER_VECTOR_PAGES", True):
            return 0

        if progress_callback:
            progress_callback(
                currentDocument=os.path.basename(path),
                documentPhase="Selecting visual PDF pages",
            )
        try:
            with PDF_NATIVE_LOCK:
                rendered_pages = self.render_pdf_visual_pages(
                    path,
                    max_pages=int(self.config.get("PDF_RENDER_MAX_PAGES_PER_DOC", 8) or 0),
                    min_drawings=int(self.config.get("PDF_RENDER_MIN_DRAWINGS", 100) or 100),
                    zoom=float(self.config.get("PDF_RENDER_ZOOM", 1.5) or 1.5),
                    render_raster_pages=bool(self.config.get("PDF_RENDER_RASTER_PAGES", True)),
                    min_raster_coverage=float(self.config.get("PDF_RENDER_MIN_RASTER_COVERAGE", 0.8) or 0.8),
                )
        except Exception as exc:
            self.trace_logger.warning(f"⚠️ Could not render visual PDF pages for {path}: {exc}")
            return 0

        render_ocr_enabled = bool(self.config.get("PDF_RENDER_OCR_PAGES", True))
        min_text_chars = int(self.config.get("OCR_INDEX_TEXT_MIN_CHARS", 80) or 80)
        ocr_chunk_lists_available = extra_chunks is not None and extra_sources is not None and extra_meta is not None

        for rendered_page in rendered_pages:
            if progress_callback:
                progress_callback(
                    currentDocument=os.path.basename(path),
                    documentPhase="Saving rendered PDF pages",
                    pdfPage=rendered_page.page_number,
                )
            target_state.add_image_store(
                rendered_page.image_key,
                base64.b64encode(rendered_page.image_bytes).decode("utf-8"),
            )
            target_state.add_image_caption(rendered_page.image_key, rendered_page.caption)

            searchable_text = (rendered_page.searchable_text or "").strip()
            source_text = self.rendered_page_source_text(rendered_page)
            if render_ocr_enabled and len(source_text) < min_text_chars:
                ocr_result = self.ocr_image_bytes(rendered_page.image_bytes, rendered_page.image_key)
                if ocr_result["accepted"]:
                    ocr_text = ocr_result["text"]
                    searchable_text = "\n".join(part for part in [searchable_text, ocr_text] if part).strip()
                    score = ocr_result["score"]
                    confidence = ocr_result["confidence"]
                    self.trace_logger.info(
                        f"🧠 Rendered page OCR accepted for {rendered_page.image_key}: "
                        f"{len(ocr_text)} chars | score: {score:.2f}{self.format_confidence(confidence)}"
                    )
                    if (
                        ocr_chunk_lists_available
                        and self.config.get("INDEX_IMAGE_OCR_AS_TEXT", False)
                        and len(ocr_text) >= min_text_chars
                    ):
                        extra_chunks.append(ocr_text)
                        extra_sources.append(path)
                        ocr_meta = self.chunker.make_chunk_meta(ocr_text, path, "Rendered Page OCR", "ocr")
                        ocr_meta.update({
                            "page": rendered_page.page_number,
                            "parent_source": path,
                            "source_image_id": rendered_page.image_key,
                            "ocr_score": score,
                            "ocr_confidence": confidence,
                        })
                        extra_meta.append(ocr_meta)
                else:
                    log_fn = self.trace_logger.debug if ocr_result["skipped"] else self.trace_logger.warning
                    log_fn(
                        f"⚠️ Stored rendered page {rendered_page.image_key} without extra OCR text — "
                        f"OCR score: {ocr_result['score']:.2f}, reason: {ocr_result['reason']}"
                    )

            if searchable_text:
                target_state.add_image_page_text(rendered_page.image_key, searchable_text)

        if rendered_pages:
            self.trace_logger.info(f"🖼️ Rendered {len(rendered_pages)} vector-heavy PDF pages for {os.path.basename(path)}")
        return len(rendered_pages)

    def pdf_embedded_image_ocr_config(self):
        config = dict(getattr(self.config, "config", self.config))
        config["OCR_MIN_IMAGE_WIDTH"] = max(
            int(config.get("OCR_MIN_IMAGE_WIDTH", 20) or 20),
            int(config.get("PDF_EMBEDDED_IMAGE_OCR_MIN_WIDTH", 80) or 80),
        )
        config["OCR_MIN_IMAGE_HEIGHT"] = max(
            int(config.get("OCR_MIN_IMAGE_HEIGHT", 20) or 20),
            int(config.get("PDF_EMBEDDED_IMAGE_OCR_MIN_HEIGHT", 80) or 80),
        )
        config["OCR_MIN_IMAGE_AREA"] = max(
            int(config.get("OCR_MIN_IMAGE_AREA", 900) or 900),
            int(config.get("PDF_EMBEDDED_IMAGE_OCR_MIN_AREA", 6400) or 6400),
        )
        return config

    def should_queue_pdf_image_dimensions(self, width, height):
        if width <= 0 or height <= 0:
            return True, ""
        skip, reason = should_skip_image_dimensions(width, height, self.pdf_embedded_image_ocr_config())
        return not skip, reason

    def load_pdf_text(self, path, target_state=None, progress_callback=None):
        target_state = target_state or self.state
        self.trace_logger.info(f"📅 Loading PDF: {path}")
        page_texts = []
        extra_chunks, extra_sources, extra_meta = [], [], []
        image_jobs = []
        seen_image_xrefs = set()
        skipped_image_candidates = 0
        duplicate_image_candidates = 0

        with PDF_NATIVE_LOCK:
            pdf = fitz.open(path)
            try:
                total_pages = len(pdf)
                last_reported_page = 0
                for page_num in range(total_pages):
                    page_number = page_num + 1
                    if progress_callback and self.should_report_page_progress(page_number, total_pages, last_reported_page):
                        last_reported_page = page_number
                        progress_callback(
                            currentDocument=os.path.basename(path),
                            documentPhase="Scanning PDF pages",
                            pdfPage=page_number,
                            pdfPages=total_pages,
                            imageCandidates=len(image_jobs),
                            skippedImageCandidates=skipped_image_candidates,
                            duplicateImageCandidates=duplicate_image_candidates,
                        )
                    page = pdf[page_num]
                    page_text = page.get_text().strip()
                    page_texts.append(page_text)

                    for img_index, img in enumerate(page.get_images(full=True)):
                        try:
                            xref = img[0]
                            if xref in seen_image_xrefs:
                                duplicate_image_candidates += 1
                                continue
                            seen_image_xrefs.add(xref)
                            image_width = int(img[2] or 0) if len(img) > 3 else 0
                            image_height = int(img[3] or 0) if len(img) > 3 else 0
                            should_queue, reason = self.should_queue_pdf_image_dimensions(image_width, image_height)
                            if not should_queue:
                                skipped_image_candidates += 1
                                self.trace_logger.debug(
                                    f"⚠️ Skipping embedded PDF image on page {page_number} before extraction: {reason}"
                                )
                                continue
                            base_image = pdf.extract_image(xref)
                            base_width = int(base_image.get("width") or image_width)
                            base_height = int(base_image.get("height") or image_height)
                            should_queue, reason = self.should_queue_pdf_image_dimensions(base_width, base_height)
                            if not should_queue:
                                skipped_image_candidates += 1
                                self.trace_logger.debug(
                                    f"⚠️ Skipping embedded PDF image on page {page_number} before OCR: {reason}"
                                )
                                continue
                            image_bytes = base_image["image"]
                            img_name = f"{os.path.basename(path)}_page{page_number}_img{img_index+1}"
                            image_jobs.append((len(image_jobs), page_num, img_index, image_bytes, img_name))
                        except Exception as exc:
                            self.trace_logger.warning(f"❌ Failed to process image on page {page_number}: {exc}")
                            continue
            finally:
                pdf.close()

        if progress_callback:
            progress_callback(
                currentDocument=os.path.basename(path),
                documentPhase="OCR image extraction",
                pdfPage=total_pages,
                pdfPages=total_pages,
                imageCandidates=len(image_jobs),
                skippedImageCandidates=skipped_image_candidates,
                duplicateImageCandidates=duplicate_image_candidates,
            )
        if skipped_image_candidates or duplicate_image_candidates:
            self.trace_logger.info(
                f"🧹 PDF image prefilter for {os.path.basename(path)}: "
                f"{len(image_jobs)} queued, {skipped_image_candidates} tiny/invalid skipped, "
                f"{duplicate_image_candidates} duplicate xrefs skipped."
            )
        for result in self.run_pdf_image_ocr_jobs(image_jobs):
            page_num = result["page_num"]
            img_name = result["img_name"]
            ocr_result = result["ocr_result"]
            web_image_bytes = result["web_image_bytes"]

            target_state.add_image_store(img_name, base64.b64encode(web_image_bytes).decode("utf-8"))
            target_state.add_image_caption(img_name, f"Image from {os.path.basename(path)}, page {page_num+1}")

            if not ocr_result["accepted"]:
                log_fn = self.trace_logger.debug if ocr_result["skipped"] else self.trace_logger.warning
                score = ocr_result["score"]
                reason = ocr_result["reason"]
                log_fn(f"⚠️ Stored {img_name} without searchable OCR text — OCR score: {score:.2f}, reason: {reason}")
                continue

            ocr_text = ocr_result["text"]
            score = ocr_result["score"]
            confidence = ocr_result["confidence"]

            self.trace_logger.info(
                f"🧠 OCR accepted for {img_name}: {len(ocr_text)} chars | "
                f"score: {score:.2f}{self.format_confidence(confidence)}"
            )

            target_state.add_image_page_text(img_name, ocr_text)
            if self.config.get("INDEX_IMAGE_OCR_AS_TEXT", False) and len(ocr_text) >= self.config.get("OCR_INDEX_TEXT_MIN_CHARS", 80):
                extra_chunks.append(ocr_text)
                extra_sources.append(path)
                ocr_meta = self.chunker.make_chunk_meta(ocr_text, path, "Image OCR", "ocr")
                ocr_meta.update({
                    "page": page_num + 1,
                    "parent_source": path,
                    "source_image_id": img_name,
                    "ocr_score": score,
                    "ocr_confidence": confidence,
                })
                extra_meta.append(ocr_meta)

        self.add_pdf_rendered_pages(
            path,
            target_state,
            progress_callback=progress_callback,
            extra_chunks=extra_chunks,
            extra_sources=extra_sources,
            extra_meta=extra_meta,
        )
        return page_texts, extra_chunks, extra_sources, extra_meta

    def extract_images_from_docx_textboxes(self, path):
        base_doc = os.path.basename(path)
        all_chunks = []
        all_meta = []

        try:
            with open(path, "rb") as file:
                docx_content = file.read()
            with zipfile.ZipFile(BytesIO(docx_content)) as docx_zip:
                rels = {}
                for name in docx_zip.namelist():
                    if name.startswith("word/_rels/") and name.endswith(".xml.rels"):
                        rel_tree = etree.fromstring(docx_zip.read(name))
                        for rel in rel_tree.xpath(
                            "//rel:Relationship",
                            namespaces={"rel": "http://schemas.openxmlformats.org/package/2006/relationships"},
                        ):
                            rid = rel.attrib["Id"]
                            target = rel.attrib["Target"]
                            rels[rid] = os.path.normpath(os.path.join(os.path.dirname(name), target))

                document_xml = docx_zip.read("word/document.xml")
                tree = etree.fromstring(document_xml)
                namespaces = {
                    "v": "urn:schemas-microsoft-com:vml",
                    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
                }

                v_images = tree.xpath(".//v:imagedata", namespaces=namespaces)
                for idx, v_img in enumerate(v_images):
                    r_embed = v_img.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
                    if r_embed and r_embed in rels:
                        img_path = "word/" + rels[r_embed].replace("\\", "/")
                        if img_path in docx_zip.namelist():
                            img_data = docx_zip.read(img_path)
                            img_name = f"{base_doc}_textbox_img{idx+1}"

                            try:
                                ocr_result = self.ocr_image_bytes(img_data, img_name)
                                if not ocr_result["accepted"]:
                                    log_fn = self.trace_logger.debug if ocr_result["skipped"] else self.trace_logger.warning
                                    log_fn(
                                        f"⚠️ Dropping textbox image {img_name} due to low OCR quality: "
                                        f"{ocr_result['score']:.2f} | {ocr_result['reason']}"
                                    )
                                    continue
                                ocr_text = ocr_result["text"]
                                web_img_data = self.image_bytes_to_png_bytes(img_data, img_name)
                                self.state.add_image_store(img_name, base64.b64encode(web_img_data).decode("utf-8"))
                                self.state.add_image_caption(img_name, f"Textbox image in {base_doc}")
                                self.state.add_image_page_text(img_name, ocr_text)

                                score = ocr_result["score"]
                                confidence = ocr_result["confidence"]
                                use_adaptive = self.config.get("USE_ADAPTIVE_CHUNKING", False)
                                self.trace_logger.info(
                                    f"🧠 Textbox OCR accepted for {img_name}: {len(ocr_text)} chars | "
                                    f"score: {score:.2f}{self.format_confidence(confidence)} Using Adaptive: {use_adaptive}"
                                )
                                if use_adaptive:
                                    chunks, meta = self.chunker.adaptive_chunk_text(ocr_text, base_doc)
                                else:
                                    chunks, meta = self.chunker.smart_chunk_text(ocr_text, base_doc)

                                for item in meta:
                                    ocr_meta = self.chunker.make_chunk_meta(
                                        ocr_text,
                                        base_doc,
                                        "Textbox OCR",
                                        "ocr",
                                    )
                                    ocr_meta.update(item)
                                    ocr_meta.update({
                                        "section": "Textbox OCR",
                                        "source_image_id": img_name,
                                        "ocr_score": score,
                                        "ocr_confidence": confidence,
                                        "source": base_doc,
                                    })
                                    item.clear()
                                    item.update(ocr_meta)

                                all_chunks.extend(chunks)
                                all_meta.extend(meta)
                            except Exception as exc:
                                self.trace_logger.warning(f"⚠️ Failed OCR for DOCX textbox {img_name}: {exc}")

            return all_chunks, all_meta
        except Exception as exc:
            self.trace_logger.warning(f"❌ Failed to extract DOCX textbox images from {path}: {exc}")
            return [], []

    @staticmethod
    def extract_page_number(value):
        match = re.search(r"_page(\d+)", value)
        return int(match.group(1)) if match else 0

    @staticmethod
    def extract_first_number(value):
        match = re.search(r"(\d+)", value)
        return int(match.group(1)) if match else 0

    def process_docx_file(self, fpath, target_state, trace_logger, chunker, token_utils):
        doc = Document(fpath)
        text = "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
        density = token_utils.estimate_token_density(text)
        if density > 40:
            trace_logger.warning(f"⚠️ High token density in {fpath}: {density:.2f} tokens/line")

        use_adaptive = self.config.get("USE_ADAPTIVE_CHUNKING", False)
        if use_adaptive:
            chunks, meta = chunker.adaptive_chunk_text(text, fpath)
        else:
            chunks, meta = chunker.smart_chunk_text(text, fpath)

        target_state.extend_chunks(chunks, [fpath] * len(chunks), meta)
        img_chunks, img_meta = self.extract_images_from_docx_textboxes(fpath)
        target_state.extend_chunks(img_chunks, [fpath] * len(img_chunks), img_meta)

    def process_pdf_file(self, fpath, target_state, trace_logger, chunker, token_utils, progress_callback=None):
        page_texts, img_chunks, img_sources, img_meta = self.load_pdf_text(
            fpath,
            target_state,
            progress_callback=progress_callback,
        )
        text = "\n\n".join(page_texts)
        density = token_utils.estimate_token_density(text)
        if density > 40:
            trace_logger.warning(f"⚠️ High token density in {fpath}: {density:.2f} tokens/line")

        use_adaptive = self.config.get("USE_ADAPTIVE_CHUNKING", False)
        if use_adaptive:
            chunks, meta = chunker.adaptive_chunk_pages(page_texts, fpath)
        else:
            chunks, meta = chunker.smart_chunk_pages(page_texts, fpath)

        linked_visuals = self.link_chunks_to_rendered_pages(
            chunks,
            meta,
            fpath,
            target_state.get_image_store().keys(),
        )
        if linked_visuals:
            trace_logger.info(f"🔗 Linked {linked_visuals} text chunks to rendered PDF page images for {os.path.basename(fpath)}")

        target_state.extend_chunks(chunks + img_chunks, [fpath] * len(chunks) + img_sources, meta + img_meta)

    def process_text_file(self, fpath, target_state, trace_logger, chunker, token_utils):
        try:
            with open(fpath, "r", encoding="utf-8") as file:
                text = file.read()

            density = token_utils.estimate_token_density(text)
            if density > 40:
                trace_logger.warning(f"⚠️ High token density in {fpath}: {density:.2f} tokens/line")

            use_adaptive = self.config.get("USE_ADAPTIVE_CHUNKING", False)
            if use_adaptive:
                chunks, meta = chunker.adaptive_chunk_text(text, fpath)
            else:
                chunks, meta = chunker.smart_chunk_text(text, fpath)

            target_state.extend_chunks(chunks, [fpath] * len(chunks), meta)
            trace_logger.info(f"✅ Processed text file: {fpath}")
        except Exception as exc:
            trace_logger.error(f"❌ Failed to process text file {fpath}: {exc}")

    def process_image_file(self, fpath, target_state, trace_logger, chunker, token_utils=None):
        try:
            with open(fpath, "rb") as img_file:
                img_data = img_file.read()

            img_name = os.path.basename(fpath)
            ocr_result = self.ocr_image_bytes(img_data, img_name)
            if not ocr_result["accepted"]:
                log_fn = trace_logger.debug if ocr_result["skipped"] else trace_logger.warning
                log_fn(f"⚠️ Dropped {img_name} due to low OCR quality: {ocr_result['score']:.2f} | {ocr_result['reason']}")
                return

            ocr_text = ocr_result["text"]
            score = ocr_result["score"]
            confidence = ocr_result["confidence"]
            web_img_data = self.image_bytes_to_png_bytes(img_data, img_name)
            target_state.add_image_store(img_name, base64.b64encode(web_img_data).decode("utf-8"))
            target_state.add_image_caption(img_name, f"Image: {img_name}")
            target_state.add_image_page_text(img_name, ocr_text)
            target_state.add_image_id(img_name)

            trace_logger.info(
                f"🧠 OCR accepted for {img_name}: {len(ocr_text)} chars | "
                f"score: {score:.2f}{self.format_confidence(confidence)}"
            )

            use_adaptive = self.config.get("USE_ADAPTIVE_CHUNKING", False)
            if use_adaptive:
                chunks, meta = chunker.adaptive_chunk_text(ocr_text, img_name)
            else:
                chunks, meta = chunker.smart_chunk_text(ocr_text, img_name)

            for item in meta:
                ocr_meta = chunker.make_chunk_meta(
                    ocr_text,
                    img_name,
                    "Image OCR",
                    "ocr",
                )
                ocr_meta.update(item)
                ocr_meta.update({
                    "section": "Image OCR",
                    "source_image_id": img_name,
                    "ocr_score": score,
                    "ocr_confidence": confidence,
                    "source": img_name,
                })
                item.clear()
                item.update(ocr_meta)

            target_state.extend_chunks(chunks, [img_name] * len(chunks), meta)
            trace_logger.info(f"✅ Processed image file: {fpath}")
        except Exception as exc:
            trace_logger.error(f"❌ Failed to process image file {fpath}: {exc}")

    def process_file_by_type(self, fpath, target_state, trace_logger, chunker, token_utils, progress_callback=None):
        if os.path.isdir(fpath):
            trace_logger.warning(f"⚠️ Skipping directory: {fpath}")
            return

        ext = os.path.splitext(fpath)[1].lower()
        trace_logger.debug(f"Processing file: {fpath} with extension: {ext}")

        if ext == self.pdf_ext:
            self.process_pdf_file(fpath, target_state, trace_logger, chunker, token_utils, progress_callback=progress_callback)
        elif ext == ".docx":
            self.process_docx_file(fpath, target_state, trace_logger, chunker, token_utils)
        elif ext in {".md", ".txt"}:
            self.process_text_file(fpath, target_state, trace_logger, chunker, token_utils)
        elif ext in {".png", ".jpg", ".jpeg"}:
            self.process_image_file(fpath, target_state, trace_logger, chunker, token_utils)
        else:
            trace_logger.warning(f"⚠️ Unsupported file type: {ext} for File: {fpath}")

    def load_documents_parallel(
        self,
        folder,
        files_selected,
        clear_existing=True,
        target_state=None,
        target_chunker=None,
        target_token_utils=None,
        progress_callback=None,
    ):
        target_state = target_state or self.state
        target_chunker = target_chunker or self.chunker
        target_token_utils = target_token_utils or self.token_utils
        self.trace_logger.info(f"⚡ Starting threaded document loading from '{folder}'")

        if not os.path.exists(folder):
            self.trace_logger.error("❌ Training folder not found.")
            return

        if isinstance(files_selected, list):
            file_list = files_selected
        else:
            file_list = []
            recursive = self.config.get("TRAINING_RECURSIVE", True)
            excluded_dirs = set(self.config.get("TRAINING_EXCLUDE_DIRS", []))

            if recursive:
                for root, dirnames, filenames in os.walk(folder):
                    dirnames[:] = [
                        dirname for dirname in dirnames
                        if dirname not in excluded_dirs
                        and os.path.relpath(os.path.join(root, dirname), folder) not in excluded_dirs
                    ]
                    for filename in filenames:
                        if filename.startswith("~$"):
                            continue
                        fpath = os.path.join(root, filename)
                        if os.path.getsize(fpath) > 0:
                            file_list.append(os.path.relpath(fpath, folder))
            else:
                file_list = [
                    filename for filename in os.listdir(folder)
                    if not filename.startswith("~$")
                    and os.path.isfile(os.path.join(folder, filename))
                    and os.path.getsize(os.path.join(folder, filename)) > 0
                ]

        file_list.sort(key=self.extract_first_number)
        if progress_callback:
            progress_callback(stage="processing_documents", total_files=len(file_list))
        if clear_existing:
            target_state.clear_all()

        if not file_list:
            self.trace_logger.warning(f"⚠️ No supported documents found in '{folder}'.")
            return

        def process_file(filename):
            fpath = filename if os.path.isabs(filename) else os.path.join(folder, filename)
            active_count = self.begin_document_worker()
            try:
                if progress_callback:
                    progress_callback(stage="processing_documents", current_file=filename)
                thread_id = threading.get_ident()
                self.trace_logger.info(f"🛠️ Thread-{thread_id} started for {filename} ({active_count} active document workers)")
                start = time.time()

                detail_progress = None
                if progress_callback:
                    def detail_progress(**details):
                        progress_callback(stage="processing_documents", current_file=filename, file_details=details)

                self.process_file_by_type(
                    fpath,
                    target_state,
                    self.trace_logger,
                    target_chunker,
                    target_token_utils,
                    progress_callback=detail_progress,
                )

                elapsed = time.time() - start
                self.trace_logger.info(f"✅ Thread-{thread_id} finished {filename} in {elapsed:.2f}s")
            except Exception as exc:
                self.trace_logger.error(f"❌ Error processing {filename}: {exc}")
            finally:
                if progress_callback:
                    progress_callback(stage="processing_documents", finished_file=filename)
                self.finish_document_worker()

        cpu_count = self.detected_cpu_count()
        max_workers = self.document_worker_count(len(file_list), cpu_count=cpu_count)
        self.trace_logger.info(
            f"⚙️ Ingest worker budget: {cpu_count} cores detected, reserving {self.reserved_core_count(cpu_count)}, "
            f"{self.usable_core_count(cpu_count)} usable, {max_workers} document workers for {len(file_list)} files."
        )
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_file, filename): filename for filename in file_list}
            for future in as_completed(futures):
                future.result()

        if self.config.get("ENABLE_TOKEN_NORMALIZATION", False):
            target_token_utils.normalize_token_distribution()
        self.trace_logger.info(
            f"🚀 Finished loading. {len(target_state.get_chunks())} chunks, "
            f"{len(target_state.get_image_page_text())} accepted image OCR texts."
        )
