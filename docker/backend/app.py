from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
import os
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI()

IS_DUMMY = os.getenv("IS_FASTAPI_DUMMY", 'False').lower() in ('true', 'ture', '1', 't')
IS_HUMAN_APPROVE_LAYER = os.getenv("IS_HUMAN_APPROVE_LAYER", 'True').lower() in ('true', 'ture', '1', 't')

# S3 and Environment Config
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


if not IS_DUMMY:
    # Load model and tokenizer
    model_path = "./models/stage1" # todo: potential problem!!!
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForCausalLM.from_pretrained(model_path)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()

class GenerationRequest(BaseModel):
    prompt: str
    temperature: float = 0.7
    top_p: float = 0.95


def _generate(request: GenerationRequest):
    if IS_DUMMY:
        return {"prediction": f"<|user|>\n{request.prompt}\n<|assistant|>\nThis is a dummy response.", "probability": 1.0}

    formatted_prompt = f"<|user|>\n{request.prompt}\n<|assistant|>\n"
    inputs = tokenizer(formatted_prompt, return_tensors="pt").to(device)

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=128,
            do_sample=True,
            top_p=request.top_p,
            temperature=request.temperature,
            repetition_penalty=1.2,
            pad_token_id=tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id
        )

    generated = tokenizer.decode(output_ids[0], skip_special_tokens=True)
    return {"prediction": generated, "probability": 1.0}

@app.post("/generate")
def generate(request: GenerationRequest):
    if not request.prompt:
        raise HTTPException(status_code=400, detail="No prompt provided")

    if IS_HUMAN_APPROVE_LAYER:
        session_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

        reply = _generate(request)

        obj = {
            "prompt": req.prompt,
            "response": reply,
            "timestamp": timestamp
        }
        s3_key = f"conversation_logs/{session_id}.json"

        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=json.dumps(obj),
            ContentType="application/json"
        )

        s3.put_object_tagging(
            Bucket=BUCKET_NAME, Key=s3_key,
            Tagging={'TagSet': [{'Key': 'status', 'Value': 'needs_review'}]})

        return {"session_id": session_id,
                "placeholder": "待醫師審核"}

    return _generate(request)

Instrumentator().instrument(app).expose(app)
