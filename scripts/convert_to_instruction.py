import json

# Adjust these paths 
input_path = "../data_clean/questions/Taiwan/train.jsonl"
output_path = "../data/medical_qa_with_answer_text.jsonl"

converted = []

# Load and convert data 
with open(input_path, "r", encoding="utf-8") as infile:
    for line in infile:
        item = json.loads(line)
        question = item.get("question", "").strip()
        options = item.get("options", {})
        answer_idx = item.get("answer_idx", "").strip()
        answer_text = item.get("answer", "").strip()

        if not question or not options or not answer_idx or not answer_text:
            continue  # skip incomplete entries

        # Convert options dict into A: xxx\nB: xxx...
        formatted_options = "\n".join([f"{k}: {v}" for k, v in options.items()])
        
        # Format instruction
        prompt = (
            f"你是一位專業的台語醫療諮詢助理。請根據下列問題及選項，用口語化的方式簡單回覆正確答案並說明理由。\n"
            f"Q: {question}\n{formatted_options}\n請選出正確答案並說明理由。"
            )

        # Combine letter and answer text
        answer_label = options.get(answer_idx, "").strip()
        full_output = f"A: {answer_label}。{answer_text} <END>" #add <END> to prevent model to repeat the answer

        converted.append({
            "instruction": prompt,
            "input": "",
            "output": full_output
        })

# Save as .jsonl
with open(output_path, "w", encoding="utf-8") as outfile:
    for item in converted:
        outfile.write(json.dumps(item, ensure_ascii = False) + "\n")

print(f"Done! Converted {len(converted)} items to {output_path}")