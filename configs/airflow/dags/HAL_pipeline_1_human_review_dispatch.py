# dags/HAL_pipeline_1_human_review_dispatch.py
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

# ─────────────── Basic Configuration ───────────────
BUCKET = os.getenv("BUCKET_NAME", "production")
LABEL_STUDIO_URL = os.environ["LABEL_STUDIO_URL"].rstrip("/")
LS_TOKEN = os.environ["LABEL_STUDIO_USER_TOKEN"]
PROJECT_TITLE = "Taigi Medical LLM Doctor Review"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Maximum minutes to wait for doctor annotation
MAX_WAIT_MINUTES = int(os.getenv("MAX_WAIT_MINUTES", 60))

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# ─────────────── Shared Utilities ───────────────
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

# ─────────────── Task 1: Retrieve sessions pending review ───────────────
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

                # Skip entries without a session_id
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
    # Return boolean for ShortCircuitOperator
    return bool(pending)

# ─────────────── Task 2: Ensure Label Studio project exists ───────────────
def ensure_ls_project(**context):
    """Create Label Studio project if not exists; save project_id to XCom."""
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

# ─────────────── Task 3: Import pending sessions into Label Studio ───────────────
def import_tasks_to_ls(**context):
    pending = context["ti"].xcom_pull(key="pending", task_ids="list_pending_sessions")
    project_id = context["ti"].xcom_pull(key="project_id", task_ids="ensure_ls_project")
    if not pending:
        logger.info("No pending sessions to import.")
        return

    imported_keys = set()
    resp = requests.get(
        f"{LABEL_STUDIO_URL}/api/projects/{project_id}/tasks",
        headers=ls_headers()
    )
    resp.raise_for_status()
    for t in resp.json():
        s3_key = t.get("meta", {}).get("s3_key")
        if s3_key:
            imported_keys.add(s3_key)

    # filter um imported pending
    to_import = [
        item for item in pending
        if item["key"] not in imported_keys
    ]

    if not to_import:
        logger.info("All pending sessions already imported to Label Studio.")
        return

    tasks = [
        {
            "data": {"prompt": item["prompt"], "response": item["response"]},
            "meta": {"s3_key": item["key"]},
        }
        for item in to_import
    ]

    r = requests.post(
        f"{LABEL_STUDIO_URL}/api/projects/{project_id}/import",
        headers=ls_headers(),
        json=tasks,
    )
    r.raise_for_status()
    logger.info(f"Imported {len(tasks)} new tasks to project {project_id}")

# ─────────────── DAG Definition ───────────────
with DAG(
    dag_id="HAL_pipeline_1_human_review_dispatch",
    description="Send LLM answers to doctors for approval",
    default_args=default_args,
    start_date=datetime(2025, 5, 10),
    schedule_interval="*/5 * * * *",  # every 30 minutes
    catchup=False,
    tags=["taigi-mlops", "HAL"],
) as dag:

    # 1. Find unreviewed sessions
    list_pending = ShortCircuitOperator(
        task_id="list_pending_sessions",
        python_callable=list_pending_sessions,
        provide_context=True,
    )

    # 2. Ensure Label Studio project exists
    ensure_project = PythonOperator(
        task_id="ensure_ls_project",
        python_callable=ensure_ls_project,
        provide_context=True,
    )

    # 3. Import tasks into Label Studio
    import_tasks = PythonOperator(
        task_id="import_tasks_to_ls",
        python_callable=import_tasks_to_ls,
        provide_context=True,
    )

    # Define task sequence
    list_pending >> ensure_project >> import_tasks