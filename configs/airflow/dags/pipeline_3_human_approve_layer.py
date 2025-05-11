# dags/doctor_review_pipeline.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
import time

import boto3
from airflow import DAG
from airflow.operators.python import PythonOperator, ShortCircuitOperator
from airflow.sensors.python import PythonSensor
import requests
from botocore.exceptions import ClientError

import logging

# ─────────────── 基本設定 ───────────────
BUCKET = os.getenv("BUCKET_NAME", "production")
LABEL_STUDIO_URL = os.environ["LABEL_STUDIO_URL"].rstrip("/")
LS_TOKEN = os.environ["LABEL_STUDIO_USER_TOKEN"]
PROJECT_TITLE = "Taigi Medical LLM Doctor Review"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# 最多等待醫師標註的分鐘數
MAX_WAIT_MINUTES = int(os.getenv("MAX_WAIT_MINUTES", 60))

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# ─────────────── 共用 util ───────────────
def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["MINIO_URL"],
        aws_access_key_id=os.environ["MINIO_USER"],
        aws_secret_access_key=os.environ["MINIO_PASSWORD"],
        region_name="us-east-1",
    )


def ls_headers():
    return {"Authorization": f"Token {LS_TOKEN}"}


# ─────────────── Task 1: 取得待審記錄 ───────────────
def list_pending_sessions(**context):
    """List objects tagged status=needs_review and push to XCom."""
    cli = s3_client()
    pending = []

    paginator = cli.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix="conversation_logs/"):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            # Read object tags
            tag_set = cli.get_object_tagging(Bucket=BUCKET, Key=key)["TagSet"]
            tags = {t["Key"]: t["Value"] for t in tag_set}
            if tags.get("status") == "needs_review":
                body = cli.get_object(Bucket=BUCKET, Key=key)["Body"].read()
                data = json.loads(body)
                logger.info(data)

                # Skip data without session id
                if data.get("session_id") is None:
                    continue

                pending.append(
                    {
                        "key": key,
                        "session_id": data.get("session_id"),
                        "prompt": data.get("prompt"),
                        "response": data.get("response"),
                    }
                )

    print(f"Found {len(pending)} sessions waiting for review")
    context["ti"].xcom_push(key="pending", value=pending)
    # 返回布林值供 ShortCircuitOperator 使用
    return bool(pending)


# ─────────────── Task 2: 確保 Label Studio 專案存在 ───────────────
def ensure_ls_project(**context):
    """Create LS project once; save project_id to XCom."""
    r = requests.get(f"{LABEL_STUDIO_URL}/api/projects", headers=ls_headers())
    r.raise_for_status()
    projects = r.json().get("results", [])
    for p in projects:
        if p["title"] == PROJECT_TITLE:
            context["ti"].xcom_push(key="project_id", value=p["id"])
            return

    # Create new project
    label_cfg = """
    <View>
      <Text name="prompt" value="$prompt"/>
      <Text name="response" value="$response"/>
      <Choices name="doctor_verdict" toName="response" choice="single">
        <Choice value="approved">Approved</Choice>
        <Choice value="rejected">Rejected</Choice>
      </Choices>
      <TextArea name="comment" toName="response" placeholder="Optional comment"/>
    </View>
    """
    payload = {"title": PROJECT_TITLE, "label_config": label_cfg}
    r = requests.post(
        f"{LABEL_STUDIO_URL}/api/projects", headers=ls_headers(), json=payload
    )
    r.raise_for_status()
    context["ti"].xcom_push(key="project_id", value=r.json()["id"])


# ─────────────── Task 3: 匯入待審資料到 Label Studio ───────────────
def import_tasks_to_ls(**context):
    pending = context["ti"].xcom_pull(key="pending", task_ids="list_pending_sessions")
    project_id = context["ti"].xcom_pull(key="project_id", task_ids="ensure_ls_project")
    if not pending:
        return

    tasks = []
    for item in pending:
        tasks.append(
            {
                "data": {
                    "prompt": item["prompt"],
                    "response": item["response"],
                },
                "meta": {"s3_key": item["key"]},
            }
        )

    r = requests.post(
        f"{LABEL_STUDIO_URL}/api/projects/{project_id}/import",
        headers=ls_headers(),
        json=tasks,
    )
    r.raise_for_status()
    print(f"Imported {len(tasks)} tasks to project {project_id}")


# ─────────────── Task 4: 等待醫師完成標註 ───────────────
def _all_tasks_completed(project_id):
    r = requests.get(
        f"{LABEL_STUDIO_URL}/api/projects/{project_id}/tasks",
        headers=ls_headers(),
        params={"completed": "false"},
    )
    r.raise_for_status()
    return len(r.json()) == 0


def wait_for_annotations(**context):
    project_id = context["ti"].xcom_pull(key="project_id", task_ids="ensure_ls_project")
    start = time.time()
    while time.time() - start < MAX_WAIT_MINUTES * 60:
        if _all_tasks_completed(project_id):
            return True
        print("Waiting for doctor annotations…")
        time.sleep(30)
    raise TimeoutError("Doctor review timed out")


# ─────────────── Task 5: 取回結果並寫回 S3 Tag ───────────────
def update_s3_tags(**context):
    cli = s3_client()
    project_id = context["ti"].xcom_pull(key="project_id", task_ids="ensure_ls_project")

    # Fetch completed tasks with annotations
    resp = requests.get(
        f"{LABEL_STUDIO_URL}/api/projects/{project_id}/tasks",
        headers=ls_headers(),
        params={"completed": "true"},
    )
    resp.raise_for_status()
    tasks = resp.json()

    for t in tasks:
        meta = t["meta"] or {}
        key = meta.get("s3_key")
        if not key:
            continue

        # Assume first annotation
        ann = t["annotations"][0]
        result = ann["result"][0]["value"]["choices"][0]  # approved / rejected
        comment = (
            ann["result"][1]["value"]["text"][0]
            if len(ann["result"]) > 1
            else ""
        )

        # Read original tag set
        tag_set = cli.get_object_tagging(Bucket=BUCKET, Key=key)["TagSet"]
        tags = {t["Key"]: t["Value"] for t in tag_set}
        tags.update(
            {
                "status": result,
                "processed": "true",
                "doctor_comment": comment[:255],  # Tag 值上限 255 bytes
            }
        )
        cli.put_object_tagging(
            Bucket=BUCKET,
            Key=key,
            Tagging={"TagSet": [{"Key": k, "Value": v} for k, v in tags.items()]},
        )
        print(f"Updated {key} → {result}")


# ─────────────── DAG Definition ───────────────
with DAG(
    dag_id="doctor_review_pipeline",
    description="Send LLM answers to doctors for approval and update MinIO tags",
    default_args=default_args,
    start_date=datetime(2025, 5, 10),
    schedule_interval="*/30 * * * *",  # every 30 minutes
    catchup=False,
    tags=["taigi-mlops"],
) as dag:

    # 1. 找到還沒審核的回覆
    list_pending = ShortCircuitOperator(
        task_id="list_pending_sessions",
        python_callable=list_pending_sessions,
        provide_context=True,
    )

    # 2. 確保 Label Studio 專案存在
    ensure_project = PythonOperator(
        task_id="ensure_ls_project",
        python_callable=ensure_ls_project,
        provide_context=True,
    )

    # 3. 匯入任務
    import_tasks = PythonOperator(
        task_id="import_tasks_to_ls",
        python_callable=import_tasks_to_ls,
        provide_context=True,
    )

    # 4. 等待醫師標註完成
    wait_annotations = PythonOperator(
        task_id="wait_for_annotations",
        python_callable=wait_for_annotations,
        provide_context=True,
    )

    # 5. 回寫 S3 Tag
    tag_update = PythonOperator(
        task_id="update_s3_tags",
        python_callable=update_s3_tags,
        provide_context=True,
    )

    # DAG 依序
    list_pending >> ensure_project >> import_tasks >> wait_annotations >> tag_update