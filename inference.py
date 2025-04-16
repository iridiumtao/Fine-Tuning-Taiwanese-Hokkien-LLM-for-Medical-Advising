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
prompt = (
    "問：感冒怎麼辦？\n"
    "答：多休息，多喝水，如有不適可服用感冒藥。\n\n"
    "問：頭痛怎麼緩解？\n"
    "答：可以使用冰敷或熱敷，保持安靜並適當休息。如持續不適，建議就醫。\n\n"
    f"問：{question}\n"
    "答："
)


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