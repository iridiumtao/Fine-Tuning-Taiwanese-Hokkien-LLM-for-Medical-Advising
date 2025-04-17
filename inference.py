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

prompt = f"""你是一位專業的醫療諮詢助理。請簡單回答下列問題，用口語話的方式回答。請直接回答，不要重複問題，也不要列出選項或再繼續問問題。
Q: {question}
A: """


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