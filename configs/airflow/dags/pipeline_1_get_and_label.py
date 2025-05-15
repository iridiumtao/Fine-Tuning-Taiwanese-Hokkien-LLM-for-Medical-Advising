# dags/pipeline_1_get_and_label.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
import random

import boto3
import requests
from airflow import DAG
from airflow.operators.python import PythonOperator
from botocore.exceptions import ClientError

# ─────────────── Configuration ───────────────
BUCKET_SRC = "production"
PREFIX_SRC   = "conversation_logs/"
BUCKET_WAIT = "production-label-wait"
BUCKET_NOISY = "production-noisy"

LABEL_STUDIO_URL = os.environ["LABEL_STUDIO_URL"].rstrip("/")
LS_TOKEN = os.environ["LABEL_STUDIO_USER_TOKEN"]
PROJECT_NAME = "Taigi Medical LLM – User‑Feedback"

SAMPLE_SIZE = 5
LOW_CONFIDENCE_THRESHOLD = 0.7

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# ─────────────── Utilities ───────────────
def s3():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["MINIO_URL"],
        aws_access_key_id=os.environ["MINIO_USER"],
        aws_secret_access_key=os.environ["MINIO_PASSWORD"],
        region_name="us-east-1",
    )


# ─────────────── Task: ensure buckets ───────────────
def ensure_buckets(**context):
    cli = s3()
    needed = {BUCKET_SRC, BUCKET_WAIT, BUCKET_NOISY}
    existing = {b["Name"] for b in cli.list_buckets()["Buckets"]}
    for b in needed - existing:
        cli.create_bucket(Bucket=b)


# ─────────────── Task: sample responses ───────────────
def sample_responses(**context):
    """
    Scan production/conversation_logs/ for JSON session files, filter by
    time window, confidence score, and S3 tag 'feedback_type'.
    Items with feedback_type == 'none' are ignored.
    Selected items (low‑confidence or dislike) are pushed to XCom:
        key='selected'  → list used for human review & copy to WAIT bucket
        key='all'       → list of *all* items in window, for later move step
    """
    cli = s3()  # helper defined elsewhere

    # ----- define time window -----
    if context["dag_run"].external_trigger:
        # manual run: last 30 minutes
        end   = datetime.now(timezone.utc)
        start = end - timedelta(minutes=30)
    else:
        start = context["data_interval_start"].astimezone(timezone.utc)
        end   = context["data_interval_end"].astimezone(timezone.utc)

    low_conf, disliked, others = [], [], []

    paginator = cli.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET_SRC, Prefix=PREFIX_SRC):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            try:
                # -------- read JSON content --------
                data = json.loads(
                    cli.get_object(Bucket=BUCKET_SRC, Key=key)["Body"].read()
                )

                # -------- read S3 object tags --------
                tag_dict = {
                    t["Key"]: t["Value"]
                    for t in cli.get_object_tagging(
                        Bucket=BUCKET_SRC, Key=key
                    )["TagSet"]
                }
                feedback_type = tag_dict.get("feedback_type", "none")  # like / dislike / none
                if feedback_type == "none":
                    continue  # skip items with no explicit feedback

                # -------- timestamp filter --------
                ts_raw = data.get("timestamp")
                if not ts_raw:
                    continue
                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                if not (start <= ts < end):
                    continue

                # -------- build item dict --------
                item = {
                    "key": key,
                    "prompt":   data.get("prompt", ""),
                    "response": data.get("response", ""),
                    "confidence": float(tag_dict.get("confidence", 1.0)),
                    "feedback":  feedback_type,  # like / dislike
                }

                # -------- categorize --------
                if item["confidence"] < LOW_CONFIDENCE_THRESHOLD:
                    low_conf.append(item)
                elif feedback_type == "dislike":
                    disliked.append(item)
                else:
                    others.append(item)  # 'like' responses above threshold

            except (ClientError, json.JSONDecodeError) as e:
                print(f"Skip {key}: {e}")

    # selected = low_conf + disliked, limited to SAMPLE_SIZE
    selected = low_conf + disliked
    if len(selected) > SAMPLE_SIZE:
        selected = random.sample(selected, SAMPLE_SIZE)

    # push to XCom
    ti = context["ti"]
    ti.xcom_push(key="selected", value=selected)
    ti.xcom_push(key="all",      value=low_conf + disliked + others)

    # log summary
    print(
        f"sample_responses → low={len(low_conf)}, "
        f"dislike={len(disliked)}, like/other={len(others)}, "
        f"selected={len(selected)}"
    )


# ─────────────── Task: move objects ───────────────
def move_objects(**context):
    cli = s3()
    selected = context["ti"].xcom_pull(task_ids="sample_responses", key="selected") or []
    all_items = context["ti"].xcom_pull(task_ids="sample_responses", key="all") or []
    selected_keys = {i["key"] for i in selected}

    for item in all_items:
        target = BUCKET_WAIT if item["key"] in selected_keys else BUCKET_NOISY
        cli.copy_object(
            Bucket=target,
            CopySource={"Bucket": BUCKET_SRC, "Key": item["key"]},
            Key=item["key"],
        )


# ─────────────── Task: ensure LS project ───────────────
def ensure_ls_project(**context):
    headers = {"Authorization": f"Token {LS_TOKEN}"}
    r = requests.get(f"{LABEL_STUDIO_URL}/api/projects", headers=headers, timeout=10)
    r.raise_for_status()
    for p in r.json().get("results", []):
        if p["title"] == PROJECT_NAME:
            context["ti"].xcom_push(key="pid", value=p["id"])
            return

    label_cfg = """
    <View>
      <Text name="response" value="$response"/>
      <Choices name="sentiment" toName="response" choice="single" showInLine="true">
        <Choice value="good">Good Response</Choice>
        <Choice value="bad">Bad Response</Choice>
      </Choices>
    </View>
    """
    res = requests.post(
        f"{LABEL_STUDIO_URL}/api/projects",
        headers=headers,
        json={"title": PROJECT_NAME, "label_config": label_cfg},
        timeout=10,
    )
    res.raise_for_status()
    context["ti"].xcom_push(key="pid", value=res.json()["id"])


# ─────────────── Task: send tasks to LS ───────────────
def import_to_ls(**context):
    """
    Pull selected responses from XCom and import them into Label Studio.
    Skip any item whose s3_key has already been imported (dedup).
    """
    # ----- Retrieve data from previous tasks -----
    selected = context["ti"].xcom_pull(
        task_ids="sample_responses", key="selected"
    ) or []
    if not selected:
        print("No selected tasks to import.")
        return

    project_id = context["ti"].xcom_pull(
        task_ids="ensure_ls_project", key="pid"
    )
    if not project_id:
        raise ValueError("Project ID not found in XCom.")

    # ----- Label Studio API setup -----
    headers = {"Authorization": f"Token {LS_TOKEN}"}

    # Get already‑imported keys for deduplication
    imported_keys = set()
    try:
        r = requests.get(
            f"{LABEL_STUDIO_URL}/api/projects/{project_id}/tasks",
            headers=headers,
            timeout=15,
        )
        if r.status_code == 200:
            for t in r.json():
                imported_keys.add(t.get("meta", {}).get("original_key"))
    except Exception as e:
        print(f"Warning: could not list existing tasks → {e}")

    # Filter out duplicates
    payload_tasks = []
    for item in selected:
        if item["key"] in imported_keys:
            continue
        payload_tasks.append(
            {
                "data": {
                    "prompt": item["prompt"],
                    "response": item["response"],
                },
                "meta": {
                    "original_key": item["key"],
                    "feedback": item["feedback"],  # like / dislike
                },
            }
        )

    if not payload_tasks:
        print("All tasks already imported; nothing new to send.")
        return

    # ----- Import tasks -----
    res = requests.post(
        f"{LABEL_STUDIO_URL}/api/projects/{project_id}/import",
        json=payload_tasks,
        headers=headers,
        timeout=30,
    )
    print("LS import response:", res.json())
    res.raise_for_status()


# ─────────────── DAG Definition ───────────────
with DAG(
    dag_id="pipeline_1_get_and_label",
    description="Sample & tag production data for human review",
    default_args=default_args,
    start_date=datetime(2025, 5, 10),
    schedule_interval="@daily",
    catchup=False,
    tags=["taigi-mlops", "feedback"],
) as dag:
    t_init = PythonOperator(task_id="ensure_buckets", python_callable=ensure_buckets)
    t_sample = PythonOperator(task_id="sample_responses", python_callable=sample_responses)
    t_move = PythonOperator(task_id="move_objects", python_callable=move_objects)
    t_project = PythonOperator(task_id="ensure_ls_project", python_callable=ensure_ls_project)
    t_import = PythonOperator(task_id="import_to_ls", python_callable=import_to_ls)

    t_init >> t_sample >> t_move
    [t_move, t_project] >> t_import