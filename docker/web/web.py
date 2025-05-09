# web.py

import gradio as gr
import requests
import os

FASTAPI_SERVER_URL = os.getenv("FASTAPI_SERVER_URL", "http://127.0.0.1:8000")
GRADIO_PORT = int(os.getenv("GRADIO_PORT", "7860"))

def chat_with_model(message, history, temperature, top_p):
    # request fast API
    payload = {
        "prompt": message,
        "temperature": temperature,
        "top_p": top_p
    }
    try:
        response = requests.post(f"{FASTAPI_SERVER_URL}/generate", json=payload)
        response.raise_for_status()
        data = response.json()
        # Extract only the assistant's reply, removing any prompt echoes
        raw = data.get('prediction', '')
        # Split on the assistant token and take the content after it
        parts = raw.split('<|assistant|>')
        reply = parts[-1].strip() if len(parts) > 1 else raw
        model_response = reply
    except Exception as e:
        model_response = f"Error: {e}"
    
    history.append((message, model_response))
    return history, ""

with gr.Blocks() as web:
    gr.Markdown("# Fine-tuned LLM Chatbot")
    chatbot = gr.Chatbot()
    msg = gr.Textbox(label="請輸入你的問題 Please enter your question：")
    with gr.Row():
        temp = gr.Slider(0, 1, value=0.7, label="Temperature")
        top_p = gr.Slider(0, 1, value=0.95, label="Top-p (Nucleus Sampling)")
    send = gr.Button("Submit")

    send.click(
        chat_with_model,
        inputs=[msg, chatbot, temp, top_p],
        outputs=[chatbot, msg]
    )

web.launch(server_name="0.0.0.0", server_port=GRADIO_PORT)
