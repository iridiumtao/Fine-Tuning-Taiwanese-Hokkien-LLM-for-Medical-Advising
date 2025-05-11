# web.py

import gradio as gr
import requests
import os
import boto3
from datetime import datetime
import uuid
import json
from typing import List, Tuple


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

HistoryType = List[Tuple[str, str]]


def chat_with_model(
    message: str,
    history: HistoryType,
    temperature: float,
    top_p: float,
    ids: List[str]
) -> Tuple[HistoryType, str, List[str]]:
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
    res_session_id = None

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

多謝你的耐心等待！

---
lir2 tshiann2 kiu5 i2-king1 sing5-kong1 e5 ki3-lok8, thai7 i1-sir1 sim2-hik8 liau2-au7 sui5 e7-tang3 tsa1-khuann3 kiat4-ko2.
sim2-hik8 uan5-sing5 liau2-au7, gun2 e7 sui5 thong1-tsai1 lir2.

to1-sia7 lir2 e5 nai7-sim1 tan2-thai7!

---
Your request has been successfully recorded. You will be able to view the results after the doctor’s review.
We will notify you as soon as the review is complete.

Thank you for your patience!

會話編號 / e7 ue7 pian1 ho7 / Session ID
{ res_session_id }
"""
            reply = text
        else:
            reply = f"Error: prediction is None and HAL is False. Data: {data}"

    except Exception as e:
        reply = f"Error: {e}"

    # Append to history
    history.append((message, reply))
    ids.append(res_session_id or session_id)

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

    # Return updated history, clear textbox, and persist session_ids
    return history, "", ids


def upload_feedback_to_s3(prompt, response, feedback_type, confidence, session_id):
    """
    Update tagging of the specific conversation log when user gives feedback.
    Always last session id for now.
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

def poll_status(
    history: HistoryType,
    ids: List[str]
) -> HistoryType:
    for _id in ids:
        print(f"[DEBUG] poll_status start, session_id={_id}")
        for i, (u, b) in enumerate(history):
            print(f"[DEBUG] history[{i}] bot={b!r}")
        try:
            resp = requests.get(f"{FASTAPI_SERVER_URL}/status/{_id}")
            resp.raise_for_status()
            data = resp.json()
            print("[DEBUG] status API data:", data)
        except Exception as e:
            print("[DEBUG] status API error:", e)
            continue

        status = data.get("status")
        if status == "pending":
            continue

        if status == "approved":
            new_reply = data.get("response", "（無內容 / No Response）")
        else:  # rejected
            reason = data.get("reason", "")
            new_reply = f"才會回應已經予醫師拒絕 / The docker has rejected the response：{reason}"

        # search for the message with session_id
        for idx, (u, b) in enumerate(history):
            if _id in b:
                print("found session", _id)
                history[idx] = (u, new_reply)
                break

    return history

# === Gradio Interface ===
with gr.Blocks() as web:
    gr.Markdown("# Fine-tuned LLM Chatbot")
    chatbot = gr.Chatbot()
    msg = gr.Textbox(label="請輸入你的問題 / tshiann2 su1-jip8 li2 e5 bun7-te5 / Please enter your question：")
    temp, top_p = gr.Slider(0, 1, value=0.7, label="Temperature"), gr.Slider(0, 1, value=0.95,
                                                                             label="Top-p (Nucleus Sampling)")
    send = gr.Button("送出 / sang3 tshut4 / Submit")
    session_ids = gr.State([])    # session_ids

    # Each send click gets a new session_id
    send.click(
        fn=chat_with_model,
        inputs=[msg, chatbot, temp, top_p, session_ids],
        outputs=[chatbot, msg, session_ids]
    )

    # Feedback buttons carry the session_id of the just-completed turn
    with gr.Row():
        check_btn = gr.Button("🔄 檢查審核狀態 / kiam2-tsa1 sim2-hik8 tsong7-thai3 / Check Status")
        like_btn = gr.Button("👍 回應良好 / hue5-ing3 liong5-ho2 / Good Response")
        dislike_btn = gr.Button("👎 回應無好 / hue5-ing3 bo5 ho2 / Bad Response")

    check_btn.click(
        fn=lambda: "🔄 當咧檢查審查中… / tng1-leh4 kiam2-tsa1 sim2-tsa1 tiong1 / Checking status",
        inputs=[],
        outputs=[check_btn]
    ).then(
        fn=poll_status,
        inputs=[chatbot, session_ids[-1]],
        outputs=[chatbot]
    ).then(
        fn=lambda: "🔄 檢查審核狀態 / kiam2-tsa1 sim2-hik8 tsong7-thai3 / Check Status",
        inputs=[],
        outputs=[check_btn]
    )

    like_btn.click(
        fn=lambda history, session_id: upload_feedback_to_s3(history[-1][0], history[-1][1], "like", 1.0, session_id),
        inputs=[chatbot, session_ids[-1]],
        outputs=[]
    ).then(
        fn=lambda: "多謝你的回饋 / to1 sia7 li2 e5 hue5 kui7 / Thank you for your feedback!",
        inputs=[],
        outputs=[like_btn]
    )

    dislike_btn.click(
        fn=lambda history, session_id: upload_feedback_to_s3(history[-1][0], history[-1][1], "dislike", 1.0,
                                                             session_id),
        inputs=[chatbot, session_ids[-1]],
        outputs=[]
    ).then(
        fn=lambda: "多謝你的回饋 / to1 sia7 li2 e5 hue5 kui7 / Thank you for your feedback!",
        inputs=[],
        outputs=[dislike_btn]
    )

web.launch(server_name="0.0.0.0", server_port=GRADIO_PORT)
