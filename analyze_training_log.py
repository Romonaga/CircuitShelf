import json
import os
from collections import Counter
import numpy as np
import matplotlib.pyplot as plt

INPUT_FILE = "trainingdata/training_output.jsonl"

# --- Utility functions ---
def tokenize(text):
    return text.strip().split()

def estimate_complexity(text):
    tokens = tokenize(text)
    length = len(tokens)
    unique_words = len(set(tokens))
    return {
        "length": length,
        "unique": unique_words,
        "type_token_ratio": unique_words / length if length else 0
    }

def bucket_complexity(length):
    if length < 10:
        return "very_short"
    elif length < 30:
        return "short"
    elif length < 60:
        return "medium"
    elif length < 100:
        return "long"
    else:
        return "very_long"

# --- Main Analysis ---
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
    print(f"\n📊 Total entries: {len(entries)}")

    q_complexities = []
    a_complexities = []
    confidence = []
    complexity_buckets = Counter()
    low_conf = 0

    for e in entries:
        q = e.get("question", "")
        a = e.get("llm_response", "")
        conf = float(e.get("confidence", 0.0))

        q_comp = estimate_complexity(q)
        a_comp = estimate_complexity(a)

        q_complexities.append(q_comp["length"])
        a_complexities.append(a_comp["length"])
        confidence.append(conf)

        bucket = bucket_complexity(q_comp["length"] + a_comp["length"])
        complexity_buckets[bucket] += 1

        if conf < 0.3:
            low_conf += 1

    print(f"📏 Avg Question Length: {np.mean(q_complexities):.1f} tokens")
    print(f"📏 Avg Answer Length: {np.mean(a_complexities):.1f} tokens")
    print(f"⚠️ Low-confidence (<0.3): {low_conf}/{len(confidence)}")
    print(f"🎯 Confidence: mean={np.mean(confidence):.2f}, min={min(confidence):.2f}, max={max(confidence):.2f}")

    return complexity_buckets, confidence

def plot_complexity_buckets(buckets):
    labels = list(buckets.keys())
    values = [buckets[k] for k in labels]

    plt.figure(figsize=(8, 5))
    plt.bar(labels, values)
    plt.title("QA Length Complexity Buckets")
    plt.ylabel("Entry Count")
    plt.xlabel("Complexity Level")
    plt.tight_layout()
    plt.show()

def plot_confidence_hist(confidences):
    plt.figure(figsize=(8, 5))
    plt.hist(confidences, bins=20, color='skyblue', edgecolor='black')
    plt.title("Confidence Score Distribution")
    plt.xlabel("Confidence")
    plt.ylabel("Frequency")
    plt.grid(True)
    plt.tight_layout()
    plt.show()

# --- Entry point ---
if __name__ == "__main__":
    if not os.path.exists(INPUT_FILE):
        print(f"❌ File not found: {INPUT_FILE}")
        exit(1)

    entries = load_entries(INPUT_FILE)
    complexity_buckets, confidences = analyze(entries)
    plot_complexity_buckets(complexity_buckets)
    plot_confidence_hist(confidences)
