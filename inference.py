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
# Test prompt
prompt = """你是一位專業的台語醫療諮詢助理，請根據下列問題，用口語化的台語簡單回答。請不要列出選項或重複問題。
範例1：
Q: 鼻水倒流會引起咳嗽嗎？
A: 鼻水倒流有時會流到喉嚨，刺激喉嚨引起咳嗽。

範例2：
Q: 胃食道逆流有咩症狀？
A: 嘴酸、胸口灼熱、吃飽後不舒服。

現在請回答下面的問題：
Q: {question}
A: 
"""


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