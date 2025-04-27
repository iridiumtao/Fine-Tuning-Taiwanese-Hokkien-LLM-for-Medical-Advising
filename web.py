import gradio as gr
import requests

FLASK_SERVER_URL = "http://127.0.0.1:5000"

def chat_with_model(message, history, temperature, top_p):
    # request Flask API
    payload = {
        "prompt": message,
        "temperature": temperature,
        "top_p": top_p
    }
    try:
        response = requests.post(f"{FLASK_SERVER_URL}/generate", json=payload)
        response.raise_for_status()
        model_response = response.json().get("response", "")
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

web.launch()
