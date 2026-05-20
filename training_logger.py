# training_logger.py

import json
import os
from datetime import datetime, timezone

class TrainingLogger:
    def __init__(self, output_path, trace_logger=None):
        self.output_path = output_path
        self.trace_logger = trace_logger
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

    def log(self, question, context, llm_response, model, sources, confidence, rerank_strategy):
        now = datetime.now(timezone.utc).isoformat()  # e.g., '2025-04-30T20:12:34.123456+00:00'
        entry = {
            "question": question,
            "context": context,
            "llm_response": llm_response,
            "model": model,            
            "sources": sources,
            "confidence": confidence,
            "rerank_strategy": rerank_strategy,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            
        }

        try:
            with open(self.output_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            if self.trace_logger:
                self.trace_logger.warning(f"❌ Failed to write training log: {e}")
            else:
                print(f"[TrainingLogger] Failed to write log: {e}")
