from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

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
        pad_token_id = tokenizer.eos_token_id
    )

# Decode
generated = tokenizer.decode(output_ids[0], skip_special_tokens = True)
print("\nModel Response:\n", generated)