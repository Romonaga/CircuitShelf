import os
import json

INPUT_FILE = "trainingdata/training_output.jsonl"
OUTPUT_FILE = "trainingdata/converted_finetune_dataset.jsonl"
INCLUDE_SOURCE = False  # Set to True to append source doc IDs in the prompt

def sanitize(text):
    return text.replace("\n", " ").replace("  ", " ").strip()

def build_prompt(question, context, sources=None):
    base_prompt = f"""You are an expert assistant. Use the following context to answer the question.

Context:
{context.strip()}

Question: {question.strip()}
Answer:"""

    if INCLUDE_SOURCE and sources:
        base_prompt += f"\n\n(Sources: {sources.strip()})"

    return base_prompt.strip()

def convert_jsonl(input_path, output_path):
    count = 0
    with open(input_path, "r", encoding="utf-8") as in_f, open(output_path, "w", encoding="utf-8") as out_f:
        for line in in_f:
            try:
                data = json.loads(line)
                question = sanitize(data.get("question", ""))
                context = sanitize(data.get("context", ""))
                answer = sanitize(data.get("llm_response", ""))
                sources = data.get("sources", "")

                if not question or not context or not answer:
                    continue

                prompt = build_prompt(question, context, sources)

                formatted = {
                    "messages": [
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": answer}
                    ]
                }

                out_f.write(json.dumps(formatted, ensure_ascii=False) + "\n")
                count += 1

            except json.JSONDecodeError:
                continue

    print(f"✅ Converted {count} records to {output_path}")

if __name__ == "__main__":
	print("WRT")
	convert_jsonl(INPUT_FILE, OUTPUT_FILE)
