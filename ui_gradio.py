# ui_gradio.py

import gradio as gr
import pandas as pd
import numpy as np
import os
from chunking_util import ChunkingUtils
from tokenize_util import TokenUtils
import re
import time
import bcrypt

class ArtivUI:
    def __init__(self, state,  config, trace_logger, chunker, get_rag_response, load_documents_parallel):
        
        self.state = state
        self.config = config
        self.trace_logger = trace_logger
        self.chunker = chunker
        self.get_rag_response = get_rag_response
        self.load_documents_parallel = load_documents_parallel
        self.cache = state.get_cache()
        self.site_name =  config.get("SITE_NAME")
        self.LLM_MODEL_OPTIONS = self.config.get("LLM_MODEL_OPTIONS")
        self.training_dir = self.config.get("TRAINING_DIR")
        self.IMG_EXTENSIONS = self.config.get("IMG_EXTENSIONS")
        

    def get_document_coverage(self):
        metadata = self.state.get_metadata()
        sources = self.state.get_sources()
        chunks = self.state.get_chunks()
        image_store = self.state.get_image_store()

        coverage = {}

        for i, meta in enumerate(metadata):
            src = meta["source"]
            if src not in coverage:
                ext = os.path.splitext(src)[1].lower()
                if ext == ".pdf":
                    ftype = "pdf"
                elif ext == ".md":
                    ftype = "markdown"
                elif ext == ".docx":
                    ftype = "docx"
                elif ext in self.IMG_EXTENSIONS:
                    ftype = "image"
                else:
                    ftype = "other"

                coverage[src] = {
                    "chunks": 0,
                    "images": 0,
                    "textbox_ocr": 0,
                    "sections": set(),
                    "pages": set(),
                    "type": ftype,
                }

            coverage[src]["chunks"] += 1
            section = meta.get("section", "Unknown")
            coverage[src]["sections"].add(section)

            page = meta.get("page")
            if isinstance(page, int) and page >= 0:
                coverage[src]["pages"].add(page)

            section_lower = section.lower()
            if section_lower in ["image", "image upload", "structured table", "detected equation", "variable definition"]:
                coverage[src]["images"] += 1
            elif section_lower == "textbox ocr":
                coverage[src]["textbox_ocr"] += 1

        # Backfill image counts based on FAISS-linked sources
        for s in sources:
            match = re.match(r"(.+?)_page\d+_img\d+\.png", s)
            if match:
                parent_doc = match.group(1)
                for key in coverage:
                    if parent_doc in key:
                        coverage[key]["images"] += 1

        rows = []
        for src, data in coverage.items():
            file_path = os.path.join(self.training_dir, src)
            width = height = size_kb = "-"
            embedding_count = self.state.count_embeddings_for_source(src)

            meta = None
            if src in image_store and isinstance(image_store[src], dict):
                meta = image_store[src]
            elif src + "_meta" in image_store:
                meta = image_store[src + "_meta"]

            if meta:
                width = meta.get("width", "-")
                height = meta.get("height", "-")
                size_kb = round(meta.get("file_size", 0) / 1024, 1)
            elif os.path.exists(file_path):
                size_kb = round(os.path.getsize(file_path) / 1024, 1)

            token_count = sum(TokenUtils.tokenize_len(chunks[i]) for i, s in enumerate(sources) if s == src)

            rows.append({
                "File": str(src),
                "Chunk Count": int(data["chunks"]),
                "Token Count": int(token_count),
                "Image Count": int(data["images"]),
                "Textbox OCR Count": int(data["textbox_ocr"]),
                "Sections": int(len(data["sections"])),
                "Pages": int(len(data["pages"])),
                "Source Type": str(data["type"]),
                "Size (KB)": float(size_kb) if isinstance(size_kb, (int, float)) else str(size_kb),
                "Width": int(width) if isinstance(width, (int, np.integer)) else str(width),
                "Height": int(height) if isinstance(height, (int, np.integer)) else str(height),
                "Embedding Count": int(embedding_count)
            })

        self.trace_logger.info(f"📊 Coverage table generated with {len(rows)} entries")

        return pd.DataFrame(rows) if rows else pd.DataFrame(columns=[
            "File", "Chunk Count", "Token Count", "Image Count", "Textbox OCR Count",
            "Sections", "Pages", "Source Type", "Size (KB)", "Width", "Height", "Embedding Count"
        ])



    def inspect_doc(self,doc_name):
        if not doc_name:
            return pd.DataFrame(columns=["Index", "Section", "Category", "Tokens", "Equation Score", "Text Preview"]), "No document selected."

            
        rows = []
        section_set = set()
        cat_counts = {"High-level Summary": 0, "Medium-level Detail": 0, "Technical Detail": 0}
        for idx, src in enumerate(self.state.get_sources()):
            if src != doc_name:
                continue
            meta = self.state.get_metadata()[idx]
            section = meta.get("section", "Unknown")
            category = meta.get("category", "Uncategorized")
            cat_counts[category] = cat_counts.get(category, 0) + 1
            section_set.add(section)
            text = self.state.get_chunks()[idx]
            rows.append({
                "Index": idx,
                "Section": section,
                "Category": category,
                "Tokens": TokenUtils.tokenize_len(text),
                "Equation Score": meta.get("equation_score", "-"),
                "Text Preview": text[:200] + "..." if len(text) > 200 else text
                
            })
        stat_summary = (
            f"Total Chunks: {len(rows)}\n"
            f"Sections: {len(section_set)}\n"
            f"Categories: {cat_counts}"
        )
        
        return pd.DataFrame(rows), stat_summary

    def get_last_trace(self,section_filter="All"):
        question = self.state.last_trace_data.get("question", "")
        strategy = self.state.last_trace_data.get("strategy", "")
        model = self.state.last_trace_data.get("model", "")
        confidence = self.state.last_trace_data.get("confidence", "")
        weighting_profile = self.state.last_trace_data.get("weighting_profile", "")
        faiss_time = self.state.last_trace_data.get("faiss_duration", "N/A")
        rerank_time = self.state.last_trace_data.get("rerank_duration", "N/A")

        chunks_to_show = self.state.last_trace_data.get("top_chunks", [])
        if section_filter != "All":
            chunks_to_show = [
                d for d in chunks_to_show
                if d.get("section") and self.state.chunk_metadata[d["index"]].get("special_section") == section_filter
            ]

        rows = []
        ocr_scores = []
        for d in chunks_to_show:
            ocr_quality = "-"
            chunk_source = d.get("source", "")
            if chunk_source in self.state.image_page_text:
                ocr_text = self.state.image_page_text[chunk_source]
                score, _ = self.chunker.evaluate_ocr_quality(ocr_text)
                ocr_quality = f"{score:.2f}"
                ocr_scores.append(score)

            rows.append({
                "Index": d["index"],
                "Score": d.get("score", "N/A"),
                "Distance": d.get("distance", "N/A"),
                "Fused Score": (
                    f"{float(d.get('score', 0)) * 0.6 + (1 - float(d.get('distance', 0)) / 15) * 0.4:.4f}"
                    if d.get("score") and d.get("distance") else "N/A"
                ),
                "Equation Score": self.state.chunk_metadata[d["index"]].get("equation_score", "-"),
                "Section": d.get("section", "Unknown"),
                "Source": d.get("source", "Unknown"),
                "Category": d.get("category", "Uncategorized"),
                "Tokens": TokenUtils.tokenize_len(d["text"]),
                "OCR Quality": ocr_quality,
                "Chunk Preview": d["text"]
            })

        avg_ocr_quality = f"{np.mean(ocr_scores):.2f}" if ocr_scores else "N/A"

        return (
            question,
            strategy,
            model,
            confidence,
            weighting_profile,
            self.state.last_trace_data.get("top_score", "N/A"),
            self.state.last_trace_data.get("second_score", "N/A"),
            self.state.last_trace_data.get("score_range", "N/A"),
            faiss_time,
            rerank_time,
            pd.DataFrame(rows),
            avg_ocr_quality
        )
    


    def launch(self, **kwargs):
        def as_chat_messages(chat_history):
            messages = []
            for turn in chat_history or []:
                if isinstance(turn, dict):
                    messages.append(turn)
                elif isinstance(turn, (list, tuple)) and len(turn) == 2:
                    q, a = turn
                    messages.append({"role": "user", "content": q})
                    messages.append({"role": "assistant", "content": a})
            return messages


        def check_password(username, password):
            users = self.config.get("USERS", {})
            if username in users:
                stored_hash = users[username].get("hashed_password", "")                
                if bcrypt.checkpw(password.encode(), stored_hash.encode()):
                    return True
            return False

        def login_user(username, password):
            success = check_password(username, password)
            if success:
                self.trace_logger.info(f"✅ Auth success for {username}")
                return (
                    gr.update(visible=False),           # auth_box
                    gr.update(visible=True),            # app_box
                    "",                                 # login_error
                    username                            # username_state
            
                    
                )
            else:
                self.trace_logger.warning(f"❌ Auth failed for {username}")
                return (
                    gr.update(visible=True),
                    gr.update(visible=False),
                    "Invalid credentials",
                    ""
                )


            
        
        def wrapped_get_rag_response(
            user_question, chat_history, show_full_text, top_k, dist_thresh,
            max_tokens, bypass_cache, strategy, model_name):

            _, chat_history_raw, sources, cache_stats, confidence, avg_time = self.get_rag_response(
                user_question, chat_history, show_full_text, top_k, dist_thresh,
                max_tokens, bypass_cache, strategy, model_name)

            return "", as_chat_messages(chat_history_raw), sources, cache_stats, confidence, avg_time, chat_history_raw
            
        defcon_ui = gr.Blocks()

        with defcon_ui:

            with gr.Tab("Assistant"):                
                username_state = gr.State(value="") 
                auth_box = gr.Column(visible=True)
                app_box = gr.Column(visible=False)
                
            with auth_box:
                gr.Markdown("## 🔐 Please log in to continue")
                username_input = gr.Textbox(label="Username")
                password_input = gr.Textbox(label="Password", type="password")
                login_error = gr.Textbox(label="Login Error", interactive=False)
                login_btn = gr.Button("Login")

                login_btn.click(
                    fn=login_user, inputs=[username_input, password_input],
                        outputs=[auth_box, app_box, login_error, username_state])
                
            with app_box:

                with gr.Row():
                    gr.Markdown(f"{self.site_name}")
                    cache_stats_output = gr.Textbox(label="Cache Status", value=self.cache.stats(), interactive=False, scale=1)
                    query_time_output = gr.Textbox(label="Average Retrieval Time", interactive=False, scale=1)
                                    
                with gr.Row():
                    gr.Markdown("### ⚙️ Settings")
                    bypass_cache = gr.Checkbox(label="Bypass Cache", value=True)
                    show_full_text = gr.Checkbox(label="Show Full Image Text", value=False)
                
                with gr.Row():
                    gr.Markdown("### 🧠 RAG Settings")
                    top_k_slider = gr.Slider(minimum=1, maximum=50, value=15, step=1, label="Top K Retrieved")
                    dist_thresh = gr.Slider(minimum=0.0, maximum=15.0, value=4.0, step=0.1, label="Distance Threshold")
                    max_tokens_slider = gr.Slider(minimum=500, maximum=4000, value=1800, step=100, label="Max Tokens to Merge")

                with gr.Row():
                    gr.Markdown("### 🤖 Model Settings")
                    confidence_output = gr.Textbox(label="Confidence Score", interactive=False, scale=1)
                    model_selector = gr.Dropdown(label="LLM Model", choices=self.LLM_MODEL_OPTIONS, value=self.LLM_MODEL_OPTIONS[0])
                    retrieval_strategy = gr.Dropdown(label="Retrieval Strategy", choices=["FAISS only", "FAISS + CrossEncoder"], value="FAISS + CrossEncoder")
                
                with gr.Row():
                    gr.Markdown("### 💬 Chat")
                    user_input = gr.Textbox(label="Ask a question")
                    submit_btn = gr.Button("Submit")
                    clear_btn = gr.Button("Clear")
                
                with gr.Row():
                    gr.Markdown("### 📜 Response")

                    chatbot = gr.Chatbot(show_label=False, scale=3, height=500, elem_id="chatbot")
                    
                    source_output = gr.Textbox(label="Source Documents", lines=5)
                    
                chat_history = gr.State([])

                submit_btn.click(
                    fn=wrapped_get_rag_response,
                    inputs=[
                        user_input, chat_history, show_full_text, top_k_slider,
                        dist_thresh, max_tokens_slider, bypass_cache,
                        retrieval_strategy, model_selector
                    ],
                    outputs=[
                        user_input, chatbot, source_output,
                        cache_stats_output, confidence_output, query_time_output,
                        chat_history
                    ]
                )

                user_input.submit(
                    fn=wrapped_get_rag_response,
                    inputs=[
                        user_input, chat_history, show_full_text, top_k_slider,
                        dist_thresh, max_tokens_slider, bypass_cache,
                        retrieval_strategy, model_selector
                    ],
                    outputs=[
                        user_input, chatbot, source_output,
                        cache_stats_output, confidence_output, query_time_output,
                        chat_history
                    ]
                )


                #clear_btn.click(lambda: ([], "", "", "", self.cache.stats(), "", ""), None,
                #    outputs=[chatbot, user_input, source_output, cache_stats_output, confidence_output, query_time_output])
                
                clear_btn.click(
                    fn=lambda: (
                        "", [], "", self.cache.stats(), "", "", []  # clear user_input, chatbot, source_output, and chat_history
                    ),
                    inputs=[],
                    outputs=[
                        user_input, chatbot, source_output,
                        cache_stats_output, confidence_output, query_time_output,
                        chat_history
                    ]
                )


            with gr.Tab("Coverage") as coverage_tab:
                gr.Markdown("### 📊 Document Coverage")
                coverage_table = gr.Dataframe(interactive=False, wrap=True)
                refresh_btn = gr.Button("Refresh Coverage")
                refresh_btn.click(fn=self.get_document_coverage, inputs=[], outputs=[coverage_table])

            
            with gr.Tab("Trace") as trace_tab:
                gr.Markdown("### 🧪 Query Trace Debug View")
                trace_question = gr.Textbox(label="Last Question", interactive=False)
                trace_strategy = gr.Textbox(label="Strategy", interactive=False)
                trace_model = gr.Textbox(label="LLM Model", interactive=False)
                trace_confidence = gr.Textbox(label="Confidence Score", interactive=False)
                trace_profile = gr.Textbox(label="Weighting Profile", interactive=False)
                trace_top_score = gr.Textbox(label="Top Score", interactive=False)
                trace_second_score = gr.Textbox(label="Second Score", interactive=False)
                trace_score_range = gr.Textbox(label="Score Range", interactive=False)
                trace_avg_ocr = gr.Textbox(label="Average OCR Quality", interactive=False)

                trace_section_filter = gr.Dropdown(
                    label="Filter by Special Section",
                    choices=["All", "Purpose Section", "Requirements Section", "Assumptions Section", "Constraints Section",
                             "Design Section", "Implementation Section", "Testing Section", "Results Section",
                             "Conclusion Section", "Future Work Section"],
                    value="All"
                )
                trace_faiss_time = gr.Textbox(label="FAISS Query Time", interactive=False)
                trace_rerank_time = gr.Textbox(label="Reranker Time", interactive=False)

                trace_table = gr.Dataframe(
                    value=pd.DataFrame(columns=[
                        "Index", "Score", "Distance", "Fused Score", "Equation Score", "Section", "Source",
                        "Category", "Tokens", "OCR Quality", "Chunk Preview"
                    ]),interactive=False)

        
                refresh_trace_btn = gr.Button("Refresh Trace View")
                refresh_trace_btn.click(
                    fn=lambda section: self.get_last_trace(section_filter=section),
                    inputs=[trace_section_filter],
                    outputs=[
                        trace_question, trace_strategy, trace_model, trace_confidence,
                        trace_profile, trace_top_score, trace_second_score, trace_score_range,
                        trace_faiss_time, trace_rerank_time, trace_table, trace_avg_ocr
                    ]
                )

            with gr.Tab("📂 Ingested Documents"):
                gr.Markdown("### 📂 Ingested Documents")
                doc_selector = gr.Dropdown(label="Select Document", choices=[], interactive=True)
                doc_chunk_table = gr.Dataframe(headers=["Index", "Section", "Category", "Tokens", "Text Preview"], interactive=False)
                doc_stats_box = gr.Textbox(label="Document Stats", lines=3, interactive=False)
                refresh_doc_btn = gr.Button("🔄 Refresh Document List")

                def refresh_doc_choices_on_load():
                    updated_choices = sorted(set(self.state.sources))
                    if not updated_choices:
                        return gr.update(choices=[], value=None), pd.DataFrame(columns=["Index", "Section", "Category", "Tokens", "Text Preview"]), "No document selected."

                    default_choice = updated_choices[0]
                    df, stats = self.inspect_doc(default_choice)
                    return gr.update(choices=updated_choices, value=default_choice), df, stats

                doc_selector.change(fn=self.inspect_doc, inputs=[doc_selector], outputs=[doc_chunk_table, doc_stats_box])
                refresh_doc_btn.click(fn=refresh_doc_choices_on_load, inputs=[], outputs=[doc_selector, doc_chunk_table, doc_stats_box])

                # Initial Tab Load Hooks
                initial_choices = sorted(set(self.state.sources))
                if initial_choices:
                    doc_selector.value = initial_choices[0]
                    df, stats = self.inspect_doc(initial_choices[0])
                    doc_chunk_table.value = df
                    doc_stats_box.value = stats
                else:
                    doc_selector.value = None
                    doc_chunk_table.value = pd.DataFrame(columns=["Index", "Section", "Category", "Tokens", "Text Preview"])
                    doc_stats_box.value = "No document selected."

                coverage_tab.select(fn=self.get_document_coverage, inputs=[], outputs=[coverage_table])
                trace_tab.select(
                    fn=self.get_last_trace,
                    inputs=[trace_section_filter],
                    outputs=[
                        trace_question, trace_strategy, trace_model, trace_confidence,
                        trace_profile, trace_top_score, trace_second_score, trace_score_range,
                        trace_faiss_time, trace_rerank_time, trace_table, trace_avg_ocr
                    ])

            defcon_ui.load(fn=refresh_doc_choices_on_load, inputs=[], outputs=[doc_selector, doc_chunk_table, doc_stats_box])

        kwargs.setdefault("theme", gr.themes.Default())
        defcon_ui.launch(**kwargs)
