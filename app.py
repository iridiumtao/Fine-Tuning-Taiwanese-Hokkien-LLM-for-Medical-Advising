from flask import Flask, request, jsonify
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

# Initialize Flask app
app = Flask(__name__)

# Load model and tokenizer
model_path = "models/stage1"
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForCausalLM.from_pretrained(model_path)

# Use GPU if available
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
model.eval()

# Inference function
def generate_response(prompt, temperature=0.7, top_p=0.95):
    formatted_prompt = f"<|user|>\n{prompt}\n<|assistant|>\n"
    inputs = tokenizer(formatted_prompt, return_tensors="pt").to(device)
    
    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=128,
            do_sample=True,
            top_p=top_p,
            temperature=temperature,
            repetition_penalty=1.2,
            pad_token_id=tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id
        )
    
    generated = tokenizer.decode(output_ids[0], skip_special_tokens=True)
    return generated

# API endpoint
@app.route('/generate', methods=['POST'])
def generate():
    data = request.get_json()
    prompt = data.get('prompt')
    temperature = data.get('temperature', 0.7)
    top_p = data.get('top_p', 0.95)
    
    if not prompt:
        return jsonify({'error': 'No prompt provided'}), 400
    
    response = generate_response(prompt, temperature, top_p)
    return jsonify({'response': response})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
