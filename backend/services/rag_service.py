import time
from typing import Callable

from backend.services.circuit_build_cards import build_circuit_build_card
from backend.services.conversation_manager import append_chat_turn, build_contextual_retrieval_query
from backend.services.rag_answer_finalizer import RagAnswerFinalizer
from backend.services.rag_response_helpers import (
    QueryTimingTracker,
    assemble_final_markdown,
    build_response_cache_key,
)
from backend.services.rag_retrieval import RagRetriever
from backend.services.response_cache import ResponseCacheEntry, should_cache_response


class RagService:
    def __init__(
        self,
        *,
        state,
        trace_logger,
        embedder,
        vector_store,
        chunker,
        reranker_engine,
        prompt_service,
        query_preprocessor,
        runtime_chunk_mapper,
        response_cache,
        query_log_store,
        openai_assist_service,
        document_intelligence_service,
        image_retrieval_service,
        build_source_payload: Callable[[list[dict]], list[dict]],
        query_llm: Callable,
        llm_model_options: list[str],
        default_llm_model: str,
        max_chat_history_turns: int,
        max_chat_history_chars: int,
        response_finalizer_system_prompt: str,
        response_finalizer_enabled: bool,
        response_finalizer_mode: str,
        response_finalizer_min_confidence: float,
        response_finalizer_max_context_chars: int,
    ):
        self.state = state
        self.trace_logger = trace_logger
        self.embedder = embedder
        self.vector_store = vector_store
        self.chunker = chunker
        self.reranker_engine = reranker_engine
        self.prompt_service = prompt_service
        self.query_preprocessor = query_preprocessor
        self.runtime_chunk_mapper = runtime_chunk_mapper
        self.response_cache = response_cache
        self.query_log_store = query_log_store
        self.openai_assist_service = openai_assist_service
        self.document_intelligence_service = document_intelligence_service
        self.image_retrieval_service = image_retrieval_service
        self.build_source_payload = build_source_payload
        self.query_llm = query_llm
        self.llm_model_options = llm_model_options or []
        self.default_llm_model = default_llm_model
        self.max_chat_history_turns = max_chat_history_turns
        self.max_chat_history_chars = max_chat_history_chars
        self.response_finalizer_system_prompt = response_finalizer_system_prompt
        self.response_finalizer_enabled = response_finalizer_enabled
        self.response_finalizer_mode = response_finalizer_mode
        self.response_finalizer_min_confidence = response_finalizer_min_confidence
        self.response_finalizer_max_context_chars = response_finalizer_max_context_chars
        self.query_timings = QueryTimingTracker(maxlen=100)
        self.retriever = RagRetriever(
            state=state,
            embedder=embedder,
            vector_store=vector_store,
            chunker=chunker,
            reranker_engine=reranker_engine,
            runtime_chunk_mapper=runtime_chunk_mapper,
            trace_logger=trace_logger,
        )
        self.answer_finalizer = RagAnswerFinalizer(
            openai_assist_service=openai_assist_service,
            query_llm=query_llm,
            system_prompt=response_finalizer_system_prompt,
            enabled=response_finalizer_enabled,
            mode=response_finalizer_mode,
            min_confidence=response_finalizer_min_confidence,
            max_context_chars=response_finalizer_max_context_chars,
        )

    def average_query_time(self) -> str:
        return self.query_timings.average_label()

    @staticmethod
    def assemble_final_markdown(response: str, image_blocks: list[str]) -> str:
        return assemble_final_markdown(response, image_blocks)

    def build_response_cache_key(
        self,
        *,
        entity_id=None,
        model_name,
        strategy,
        norm_q,
        retrieval_q,
        top_k,
        dist_thresh,
        max_tokens,
        show_full_text,
    ):
        return build_response_cache_key(
            vector_store=self.vector_store,
            entity_id=entity_id,
            model_name=model_name,
            strategy=strategy,
            norm_q=norm_q,
            retrieval_q=retrieval_q,
            top_k=top_k,
            dist_thresh=dist_thresh,
            max_tokens=max_tokens,
            show_full_text=show_full_text,
        )

    def get_rag_response(
        self,
        question,
        chat_history,
        show_full_text=True,
        top_k=15,
        dist_thresh=4.0,
        max_tokens=1800,
        bypass_cache=True,
        strategy="Vector + CrossEncoder",
        model_name=None,
        user_id=None,
        username=None,
        entity_id=None,
        ai_context_type="",
        ai_context_id=None,
    ):
        start_time = time.time()
        model_name = model_name or (self.llm_model_options[0] if self.llm_model_options else self.default_llm_model)
        norm_q = self.query_preprocessor.normalize(question)
        retrieval_q = self.query_preprocessor.normalize(build_contextual_retrieval_query(norm_q, chat_history))
        synonyms = self.query_preprocessor.expand(retrieval_q)
        cache_enabled = should_cache_response(chat_history, bypass_cache)
        cache_key = self.build_response_cache_key(
            entity_id=entity_id,
            model_name=model_name,
            strategy=strategy,
            norm_q=norm_q,
            retrieval_q=retrieval_q,
            top_k=top_k,
            dist_thresh=dist_thresh,
            max_tokens=max_tokens,
            show_full_text=show_full_text,
        )

        if cache_enabled:
            cached = self.response_cache.get_response(cache_key)
            if cached:
                self.trace_logger.info(f"✅ Response cache HIT: {cache_key.digest()}")
                self.query_timings.add(time.time() - start_time)
                chat_history = [list(turn) for turn in cached.chat_history]
                confidence = cached.confidence
                self.query_log_store.log_query(
                    model_name=model_name,
                    retrieval_strategy=strategy,
                    question=norm_q,
                    retrieval_query=retrieval_q,
                    elapsed_ms=int((time.time() - start_time) * 1000),
                    cache_hit=True,
                    confidence_score=confidence,
                    selected_chunks=[],
                    user_id=user_id,
                    username=username,
                )
                build_card = build_circuit_build_card(
                    norm_q,
                    cached.sources,
                    self.document_intelligence_service.for_question_and_sources(retrieval_q, cached.sources),
                    context_question=retrieval_q,
                )
                return (
                    norm_q,
                    cached.answer,
                    chat_history,
                    cached.sources,
                    self.response_cache.stats(),
                    confidence,
                    self.average_query_time(),
                    build_card,
                    None,
                )
        else:
            if bypass_cache:
                self.trace_logger.debug("Response cache bypassed by request option.")
            elif chat_history:
                self.trace_logger.debug("Response cache skipped for conversational request.")

        self.trace_logger.info(f"🔍 Response cache MISS: {cache_key.digest()} | Executing query")

        if not cache_enabled:
            self.response_cache.misses += 1

        retrieval = self.retriever.retrieve(
            synonyms=synonyms,
            retrieval_q=retrieval_q,
            top_k=top_k,
            dist_thresh=dist_thresh,
            strategy=strategy,
            entity_id=entity_id,
        )
        selected_chunks = retrieval["selected_chunks"]
        confidence = retrieval["confidence"]
        profile = retrieval["profile"]
        vector_duration = retrieval["vector_duration"]
        rerank_duration = retrieval["rerank_duration"]

        if not selected_chunks:
            response = f"No relevant documents found for: {norm_q}"
            self.trace_logger.warning(f"⚠️ No results for query: {norm_q}")
            validation_payload = None
            openai_fallback = self.openai_assist_service.answer_without_sources(
                question=norm_q,
                entity_id=entity_id,
                user_id=user_id,
                context_type=ai_context_type,
                context_id=ai_context_id,
            )
            if openai_fallback:
                response, validation_payload = openai_fallback
            chat_history = append_chat_turn(
                chat_history,
                norm_q,
                response,
                max_turns=self.max_chat_history_turns,
                max_chars=self.max_chat_history_chars,
            )
            return (
                norm_q,
                response,
                chat_history,
                [],
                self.response_cache.stats(),
                "0.00",
                self.average_query_time(),
                None,
                validation_payload,
            )

        selected_chunks = self.prompt_service.trim_chunks_to_token_budget(selected_chunks, max_tokens)
        context = "\n\n".join([chunk["text"] for chunk in selected_chunks])
        prompt = self.prompt_service.build_prompt(context, norm_q, self.chunker.is_math_heavy_question(norm_q))
        source_payload = self.build_source_payload(selected_chunks)

        response = self.query_llm(prompt, model_name, chat_history=chat_history)

        build_card = build_circuit_build_card(
            norm_q,
            source_payload,
            self.document_intelligence_service.for_question_and_sources(retrieval_q, source_payload),
            context_question=retrieval_q,
        )
        revised_response, validation = self.answer_finalizer.finalize(
            question=norm_q,
            answer=response,
            source_payload=source_payload,
            build_card=build_card,
            model_name=model_name,
            confidence=confidence,
            entity_id=entity_id,
            user_id=user_id,
            context_type=ai_context_type,
            context_id=ai_context_id,
        )

        image_md_blocks = (
            self.image_retrieval_service.build_image_markdown_blocks(retrieval_q, selected_chunks)
            if show_full_text
            else []
        )
        final_answer = self.assemble_final_markdown(revised_response, image_md_blocks)

        chat_history = append_chat_turn(
            chat_history,
            norm_q,
            revised_response,
            max_turns=self.max_chat_history_turns,
            max_chars=self.max_chat_history_chars,
        )
        if cache_enabled:
            self.response_cache.put_response(
                cache_key,
                ResponseCacheEntry(
                    answer=final_answer,
                    chat_history=[list(turn) for turn in chat_history],
                    sources=source_payload,
                    confidence=confidence,
                    metadata={
                        "model": model_name,
                        "strategy": strategy,
                        "retrieval_query": retrieval_q,
                    },
                ),
            )
        self.query_timings.add(time.time() - start_time)

        self.state.update_last_trace({
            "question": norm_q,
            "retrieval_query": retrieval_q,
            "strategy": strategy,
            "model": model_name,
            "confidence": confidence,
            "weighting_profile": profile,
            "vector_duration": f"{vector_duration:.2f}s",
            "rerank_duration": "N/A" if rerank_duration is None else f"{rerank_duration:.2f}s",
            "finalizer": validation.api_payload() if validation else None,
            "total_duration": f"{time.time() - start_time:.2f}s",
            "top_chunks": selected_chunks,
        })

        elapsed_ms = int((time.time() - start_time) * 1000)
        self.query_log_store.log_query(
            model_name=model_name,
            retrieval_strategy=strategy,
            question=norm_q,
            retrieval_query=retrieval_q,
            elapsed_ms=elapsed_ms,
            cache_hit=False,
            confidence_score=confidence,
            selected_chunks=selected_chunks,
            user_id=user_id,
            username=username,
        )

        return (
            norm_q,
            final_answer,
            chat_history,
            source_payload,
            self.response_cache.stats(),
            confidence,
            self.average_query_time(),
            build_card,
            validation.api_payload() if validation else None,
        )
