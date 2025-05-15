from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
import torch.nn.functional as F
from transformers import LlamaTokenizer, AutoModelForCausalLM

# Load model and tokenizer
model_path = "models/stage1"
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForCausalLM.from_pretrained(model_path)

# Use GPU if available
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
model.eval()

# Test prompt
question = input("請輸入你的問題：")

prompt = f"<|user|>\n{question}\n<|assistant|>\n"



# Tokenize
inputs = tokenizer(prompt, return_tensors = "pt").to(device)

# Generate
with torch.no_grad():
    output_ids = model.generate(
        **inputs,
        max_new_tokens = 128,
        do_sample = True,
        top_p = 0.95,
        temperature = 0.7,
        repetition_penalty=1.2,
        return_dict_in_generate=True,
        output_scores=True,
        pad_token_id = tokenizer.eos_token_id,
        eos_token_id = tokenizer.eos_token_id
    )

# Extract generated token ids (excluding prompt)
generated_ids = output_ids.sequences[0][inputs.input_ids.shape[-1]:]

# Extract scores (logits → probs)
logits = torch.stack(output_ids.scores, dim = 1)[0]  # shape: [num_tokens, vocab_size]
probs = F.softmax(logits, dim =- 1)
confidences = probs[range(len(generated_ids)), generated_ids]

# Decode
generated = tokenizer.decode(output_ids.sequences[0], skip_special_tokens=True)
print("\nModel Response:\n", generated)

print("\n=== Confidence per token ===")
for token_id, conf in zip(generated_ids, confidences):
    print(f"{tokenizer.decode([token_id.item()]):10s} -> {conf.item():.4f}")

avg_confidence = confidences.mean().item()
print(f"\nAverage confidence: {avg_confidence:.4f}")