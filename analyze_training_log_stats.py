import json
import os
from collections import Counter, defaultdict
import numpy as np

INPUT_FILE = "trainingdata/training_output.jsonl"

def load_entries(path):
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                item = json.loads(line)
                if item.get("question") and item.get("llm_response"):
                    entries.append(item)
            except json.JSONDecodeError:
                continue
    return entries

def analyze(entries):
    lengths = [len(e["llm_response"].split()) for e in entries]
    confs = []
    model_usage = Counter()
    rerank_usage = Counter()
    short_context = 0
    low_conf = 0

    for e in entries:
        model_usage[e.get("model", "unknown")] += 1
        rerank_usage[e.get("rerank_strategy", "unknown")] += 1

        context = e.get("context", "")
        if len(context.strip().split()) < 50:
            short_context += 1

        try:
            conf = float(e.get("confidence", 0.0))
            confs.append(conf)
            if conf < 0.3:
                low_conf += 1
        except:
            pass

    print(f"📊 Total training entries: {len(entries)}")
    print(f"✏️ Average answer length: {np.mean(lengths):.1f} words")
    print(f"📉 Min/Max answer length: {np.min(lengths)} / {np.max(lengths)} words")
    print(f"🔐 Entries with short context (<50 words): {short_context}")
    print(f"⚠️ Low-confidence entries (<0.3): {low_conf}")

    if confs:
        print(f"🎯 Confidence: mean={np.mean(confs):.2f}, min={min(confs):.2f}, max={max(confs):.2f}")

    print("\n🧠 Model Usage:")
    for model, count in model_usage.most_common():
        print(f"  - {model}: {count}")

    print("\n🔁 Rerank Strategy Usage:")
    for strat, count in rerank_usage.most_common():
        print(f"  - {strat}: {count}")

if __name__ == "__main__":
    if not os.path.exists(INPUT_FILE):
        print(f"❌ File not found: {INPUT_FILE}")
    else:
        entries = load_entries(INPUT_FILE)
        analyze(entries)