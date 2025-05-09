# web.py

import gradio as gr
import requests
import os
import boto3
from datetime import datetime
import uuid
import json

FASTAPI_SERVER_URL = os.getenv("FASTAPI_SERVER_URL", "http://127.0.0.1:8000")
GRADIO_PORT = int(os.getenv("GRADIO_PORT", "7860"))
MINIO_URL = os.getenv("MINIO_URL", "http://minio:9000")
MINIO_USER = os.getenv("MINIO_USER", "your-access-key")
MINIO_PASSWORD = os.getenv("MINIO_PASSWORD", "your-secret-key")
BUCKET_NAME = "production"

s3 = boto3.client(
    's3',
    endpoint_url=MINIO_URL,
    aws_access_key_id=MINIO_USER,
    aws_secret_access_key=MINIO_PASSWORD,
    region_name='us-east-1'
)

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

def upload_feedback_to_s3(prompt, response, feedback_type):
    timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    feedback_id = str(uuid.uuid4())
    s3_key = f"feedback/{feedback_id}.json"

    feedback_data = {
        "prompt": prompt,
        "response": response,
        "feedback_type": feedback_type,
        "timestamp": timestamp
    }

    # Upload to MinIO
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=s3_key,
        Body=json.dumps(feedback_data),
        ContentType='application/json'
    )

with gr.Blocks() as web:
    gr.Markdown("# Fine-tuned LLM Chatbot")
    chatbot = gr.Chatbot()
    msg = gr.Textbox(label="請輸入你的問題 / tshiann2 su1-jip8 li2 e5 bun7-te5 / Please enter your question：")
    with gr.Row():
        temp = gr.Slider(0, 1, value=0.7, label="Temperature")
        top_p = gr.Slider(0, 1, value=0.95, label="Top-p (Nucleus Sampling)")
    send = gr.Button("Submit")

    send.click(
        chat_with_model,
        inputs=[msg, chatbot, temp, top_p],
        outputs=[chatbot, msg]
    )

    # === Feedback Buttons ===
    with gr.Row():
        like_btn = gr.Button("👍回應良好 / hue5-ing3 liong5-ho2 / Good Response")
        dislike_btn = gr.Button("👎回應無好 / hue5-ing3 bo5 ho2 / Bad Response")
        flag_btn = gr.Button("🚩標記 / piau1-ki3 / Flag")

    like_btn.click(
        lambda history: upload_feedback_to_s3(history[-1][0], history[-1][1], "like"),
        inputs=[chatbot],
        outputs=[]
    )

    dislike_btn.click(
        lambda history: upload_feedback_to_s3(history[-1][0], history[-1][1], "dislike"),
        inputs=[chatbot],
        outputs=[]
    )

    flag_btn.click(
        lambda history: upload_feedback_to_s3(history[-1][0], history[-1][1], "flag"),
        inputs=[chatbot],
        outputs=[]
    )

web.launch(server_name="0.0.0.0", server_port=GRADIO_PORT)
