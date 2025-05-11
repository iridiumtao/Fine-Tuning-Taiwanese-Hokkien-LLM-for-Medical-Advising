# dags/HAL_pipeline_2_human_review_sync.py
from __future__ import annotations

from datetime import datetime, timedelta
import os
import json
import boto3
import requests
from airflow import DAG
from airflow.operators.python import PythonOperator, ShortCircuitOperator
from botocore.exceptions import ClientError

# ───── Env & Const ─────
BUCKET = os.getenv("BUCKET_NAME", "production")
LABEL_STUDIO_URL = os.environ["LABEL_STUDIO_URL"].rstrip("/")
LS_TOKEN = os.environ["LABEL_STUDIO_USER_TOKEN"]
PROJECT_TITLE = "Taigi Medical LLM Doctor Review"

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

# ───── Task 0: Fetch / cache project_id ─────
def get_project_id(**context):
    r = requests.get(f"{LABEL_STUDIO_URL}/api/projects", headers=ls_headers())
    r.raise_for_status()
    for p in r.json().get("results", []):
        if p["title"] == PROJECT_TITLE:
            context["ti"].xcom_push(key="project_id", value=p["id"])
            return
    raise ValueError(f"Project '{PROJECT_TITLE}' not found, ensure dispatch DAG created it")

# ───── Task 1: List completed tasks not yet synced ─────
def list_completed_tasks(**context):
    proj_id = context["ti"].xcom_pull(key="project_id", task_ids="get_project_id")
    completed = []

    url = f"{LABEL_STUDIO_URL}/api/projects/{proj_id}/tasks"
    r = requests.get(url, headers=ls_headers())
    r.raise_for_status()
    tasks = r.json()  # Label Studio returns a list directly

    for t in tasks:
        # After Label Studio task is completed, "is_labeled" is true
        if not t.get("is_labeled"):
            continue
        # Skip tasks already synced
        if t["meta"].get("synced") == "true":
            continue
        completed.append({
            "task_id": t["id"],
            "s3_key": t["meta"].get("s3_key"),
            "annotations": t["annotations"],
        })

    print(f"Found {len(completed)} completed tasks")
    context["ti"].xcom_push(key="completed", value=completed)
    # Short-circuit downstream tasks if there are none
    return bool(completed)

# ───── Task 2: Update MinIO tags and mark as synced ─────
def update_s3_and_mark(**context):
    completed = context["ti"].xcom_pull(key="completed", task_ids="list_completed_tasks")
    proj_id = context["ti"].xcom_pull(key="project_id", task_ids="get_project_id")
    cli = s3_client()

    for item in completed:
        key = item["s3_key"]
        if not key:
            continue

        # Parse doctor's decision
        ann = item["annotations"][0]  # assume first annotation
        result = ann["result"][0]["value"]["choices"][0]  # approved / rejected
        comment = (
            ann["result"][1]["value"]["text"][0]
            if len(ann["result"]) > 1
            else ""
        )

        # Update S3 object tags
        try:
            tag_set = cli.get_object_tagging(Bucket=BUCKET, Key=key)["TagSet"]
            tags = {t["Key"]: t["Value"] for t in tag_set}
            tags.update(
                {
                    "status": result,
                    "processed": "true",
                    "doctor_comment": comment[:255],
                }
            )
            cli.put_object_tagging(
                Bucket=BUCKET,
                Key=key,
                Tagging={"TagSet": [{"Key": k, "Value": v} for k, v in tags.items()]},
            )
            print(f"{key} → {result}")
        except ClientError as e:
            print(f"Failed to tag {key}: {e}")

        # Mark Label Studio task as synced to avoid reprocessing
        requests.patch(
            f"{LABEL_STUDIO_URL}/api/tasks/{item['task_id']}",
            headers=ls_headers(),
            json={"meta": {"synced": "true"}},
        )

# ───── DAG Definition ─────
default_args = {"owner": "airflow", "retries": 1, "retry_delay": timedelta(minutes=2)}

with DAG(
    dag_id="HAL_pipeline_2_human_review_sync",
    description="Every 5 min sync doctor-reviewed tasks back to MinIO",
    start_date=datetime(2025, 5, 11),
    schedule_interval="*/5 * * * *",  # every 5 minutes
    catchup=False,
    tags=["taigi-mlops", "HAL"],
    default_args=default_args,
) as dag:

    get_project = PythonOperator(
        task_id="get_project_id",
        python_callable=get_project_id,
        provide_context=True,
    )

    list_completed = ShortCircuitOperator(
        task_id="list_completed_tasks",
        python_callable=list_completed_tasks,
        provide_context=True,
    )

    update_and_mark = PythonOperator(
        task_id="update_s3_and_mark",
        python_callable=update_s3_and_mark,
        provide_context=True,
    )

    get_project >> list_completed >> update_and_mark