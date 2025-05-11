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


def chat_with_model(message, history, temperature, top_p, session_id):
    """
    Send a prompt to the FastAPI LLM server, log the conversation to S3,
    and always create a new session_id for each call.
    """
    # Always generate a fresh session_id per request
    session_id = str(uuid.uuid4())

    timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

    # Prepare payload for FastAPI
    payload = {
        "prompt": message,
        "temperature": temperature,
        "top_p": top_p,
        "session_id": session_id,
        "timestamp": timestamp
    }
    s3_key = f"conversation_logs/{session_id}.json"

    is_waiting_for_human_approve = False

    try:
        response = requests.post(f"{FASTAPI_SERVER_URL}/generate", json=payload)
        response.raise_for_status()
        data = response.json()


        if data.get('prediction') is not None: # if non-human approval required
            raw = data.get('prediction')

            # Extract assistant reply
            parts = raw.split('<|assistant|>')
            reply = parts[-1].strip() if len(parts) > 1 else raw
        elif data.get('human_approve_layer') is True:
            is_waiting_for_human_approve = True
            res_session_id = data.get('session_id')
            text = f"""
你請求已經成功的記錄，待醫師審核了後隨會當查看結果。
審核完成了後，阮會隨通知你。
會話編號：{ res_session_id }

多謝你的耐心等待！

---
lir2 tshiann2 kiu5 i2-king1 sing5-kong1 e5 ki3-lok8, thai7 i1-sir1 sim2-hik8 liau2-au7 sui5 e7-tang3 tsa1-khuann3 kiat4-ko2.
sim2-hik8 uan5-sing5 liau2-au7, gun2 e7 sui5 thong1-tsai1 lir2.
e7 ue7 pian1 ho7: { res_session_id }

to1-sia7 lir2 e5 nai7-sim1 tan2-thai7!

---
Your request has been successfully recorded. You will be able to view the results after the doctor’s review.
We will notify you as soon as the review is complete.
Session ID: { res_session_id }

Thank you for your patience!
"""
            reply = text
        else:
            reply = f"Error: prediction is None and HAL is False. Data: {data}"

    except Exception as e:
        reply = f"Error: {e}"

    # Append to history
    history.append((message, reply))

    if not is_waiting_for_human_approve:
        # Build log object
        log_obj = {
            "prompt": message,
            "temperature": temperature,
            "top_p": top_p,
            "response": reply,
            "feedback_type": "none",
            "confidence": "1.000",
            "timestamp": timestamp
        }

        # Upload the conversation log
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=json.dumps(log_obj),
            ContentType='application/json'
        )
        # Initial tagging
        s3.put_object_tagging(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Tagging={
                'TagSet': [
                    {'Key': 'session_id', 'Value': session_id},
                    {'Key': 'processed', 'Value': 'false'},
                    {'Key': 'feedback_type', 'Value': 'none'},
                    {'Key': 'confidence', 'Value': '1.000'},
                    {'Key': 'timestamp', 'Value': timestamp}
                ]
            }
        )

    # Return updated history, clear textbox, and persist session_id
    return history, "", session_id


def upload_feedback_to_s3(prompt, response, feedback_type, confidence, session_id):
    """
    Update tagging of the specific conversation log when user gives feedback.
    """
    s3_key = f"conversation_logs/{session_id}.json"
    # Fetch existing tags
    current = s3.get_object_tagging(Bucket=BUCKET_NAME, Key=s3_key)['TagSet']
    tags = {t['Key']: t['Value'] for t in current}
    # Merge new feedback tags
    tags.update({
        'processed': 'true',
        'feedback_type': feedback_type,
        'confidence': f"{confidence:.3f}"
    })

    tag_set = [{'Key': k, 'Value': v} for k, v in tags.items()]
    s3.put_object_tagging(Bucket=BUCKET_NAME, Key=s3_key, Tagging={'TagSet': tag_set})


# === Gradio Interface ===
with gr.Blocks() as web:
    gr.Markdown("# Fine-tuned LLM Chatbot")
    chatbot = gr.Chatbot()
    msg = gr.Textbox(label="請輸入你的問題 / tshiann2 su1-jip8 li2 e5 bun7-te5 / Please enter your question：")
    temp, top_p = gr.Slider(0, 1, value=0.7, label="Temperature"), gr.Slider(0, 1, value=0.95,
                                                                             label="Top-p (Nucleus Sampling)")
    send = gr.Button("送出 / sang3 tshut4 / Submit")
    session_state = gr.State("")  # 存 session_id

    # Each send click gets a new session_id
    send.click(
        fn=chat_with_model,
        inputs=[msg, chatbot, temp, top_p, session_state],
        outputs=[chatbot, msg, session_state]
    )

    # Feedback buttons carry the session_id of the just-completed turn
    with gr.Row():
        like_btn = gr.Button("👍回應良好 / hue5-ing3 liong5-ho2 / Good Response")
        dislike_btn = gr.Button("👎回應無好 / hue5-ing3 bo5 ho2 / Bad Response")

    like_btn.click(
        fn=lambda history, session_id: upload_feedback_to_s3(history[-1][0], history[-1][1], "like", 1.0, session_id),
        inputs=[chatbot, session_state],
        outputs=[]
    )

    dislike_btn.click(
        fn=lambda history, session_id: upload_feedback_to_s3(history[-1][0], history[-1][1], "dislike", 1.0,
                                                             session_id),
        inputs=[chatbot, session_state],
        outputs=[]
    )

web.launch(server_name="0.0.0.0", server_port=GRADIO_PORT)
