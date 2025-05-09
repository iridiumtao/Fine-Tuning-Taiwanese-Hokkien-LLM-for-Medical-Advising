from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta, timezone
import boto3
import os
from botocore.exceptions import ClientError
import requests

default_args = {
    'owner': 'airflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

SAMPLE_SIZE = 5
LOW_CONFIDENCE_THRESHOLD = 0.7
PROJECT_NAME = "Taigi Medical LLM"


def ensure_buckets_exist(bucket_names):
    s3 = boto3.client(
        's3',
        endpoint_url=os.environ['MINIO_URL'],
        aws_access_key_id=os.environ['MINIO_USER'],
        aws_secret_access_key=os.environ['MINIO_PASSWORD'],
        region_name="us-east-1"
    )
    existing_buckets = {b['Name'] for b in s3.list_buckets()['Buckets']}
    for bucket in bucket_names:
        if bucket not in existing_buckets:
            print(f"Creating bucket: {bucket}")
            s3.create_bucket(Bucket=bucket)
        else:
            print(f"Bucket already exists: {bucket}")


def init_buckets_task(**context):
    ensure_buckets_exist(['production-label-wait', 'production-noisy'])


def sample_production_responses(**context):
    """
    Sample LLM-generated responses from MinIO, filter them based on confidence and flags,
    and push the results to XCom for further processing in the Airflow pipeline.
    """

    # Initialize S3 client to connect to MinIO
    s3 = boto3.client(
        's3',
        endpoint_url=os.environ['MINIO_URL'],
        aws_access_key_id=os.environ['MINIO_USER'],
        aws_secret_access_key=os.environ['MINIO_PASSWORD'],
        region_name="us-east-1"
    )

    if context['dag_run'].external_trigger:
        # Manual run — use current time window
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=30)
        print("Manual trigger, using real-time window:", start, "to", end)
    else:
        # Scheduled run — use the defined data interval
        start = context['data_interval_start'].astimezone(timezone.utc)
        end = context['data_interval_end'].astimezone(timezone.utc)
        print("Scheduled run, using data interval:", start, "to", end)

    # Initialize categories for sorting responses
    low_conf = []
    flagged = []
    good_responses = []

    # Use Paginator to iterate through all objects in the 'production-responses' bucket
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket='production-responses'):
        for obj in page.get("Contents", []):
            key = obj["Key"]

            try:
                # Fetch the content of the object (the LLM response)
                response = s3.get_object(Bucket='production-responses', Key=key)
                content = response['Body'].read().decode('utf-8')

                # Retrieve the tags (metadata) associated with the object
                tags = s3.get_object_tagging(Bucket='production-responses', Key=key)['TagSet']
                tag_dict = {t['Key']: t['Value'] for t in tags}

                # Skip the object if there is no timestamp
                timestamp = tag_dict.get("timestamp")
                if not timestamp:
                    continue

                # Convert the timestamp to datetime and filter based on the defined time window
                ts = datetime.fromisoformat(timestamp)
                if not (start <= ts < end):
                    continue

                # Extract metadata values
                confidence = float(tag_dict.get("confidence", 0))
                flagged_bool = tag_dict.get("flagged") == "true"

                # Build the item dictionary for easier handling
                item = {
                    "key": key,
                    "response": content,
                    "confidence": confidence,
                    "flagged": flagged_bool
                }

                # Categorize the responses based on confidence and flags
                if confidence < LOW_CONFIDENCE_THRESHOLD:
                    low_conf.append(item)
                elif flagged_bool:
                    flagged.append(item)
                else:
                    good_responses.append(item)

            except ClientError as e:
                print(f"Error retrieving object {key}: {e}")
                continue


    # Combine low-confidence and flagged for final selection
    selected = low_conf + flagged
    # Logging the statistics of the sample
    print(f"Low confidence responses: {len(low_conf)}")
    print(f"Flagged responses: {len(flagged)}")
    print(f"Total selected for labeling: {len(selected)}")

    context['ti'].xcom_push(key='selected_responses', value=selected)
    context['ti'].xcom_push(key='all_responses', value=low_conf + flagged + good_responses)


def move_sampled_responses(**context):
    s3 = boto3.client(
        's3',
        endpoint_url=os.environ['MINIO_URL'],
        aws_access_key_id=os.environ['MINIO_USER'],
        aws_secret_access_key=os.environ['MINIO_PASSWORD'],
        region_name="us-east-1"
    )

    selected = context['ti'].xcom_pull(key='selected_responses', task_ids='sample_production_responses')
    all_items = context['ti'].xcom_pull(key='all_responses', task_ids='sample_production_responses')
    selected_keys = {item['key'] for item in selected}

    for item in all_items:
        source_key = item['key']
        target_bucket = 'production-label-wait' if source_key in selected_keys else 'production-noisy'
        s3.copy_object(
            Bucket=target_bucket,
            CopySource={'Bucket': 'production-responses', 'Key': source_key},
            Key=source_key
        )


def create_label_studio_project(**context):
    label_studio_url = os.environ['LABEL_STUDIO_URL']
    token = os.environ['LABEL_STUDIO_USER_TOKEN']
    headers = {"Authorization": f"Token {token}"}

    response = requests.get(f"{label_studio_url}/api/projects", headers=headers)
    response.raise_for_status()
    projects = response.json().get('results', [])

    for p in projects:
        if p['title'] == PROJECT_NAME:
            context['ti'].xcom_push(key='project_id', value=p['id'])
            return

    label_config = """
    <View>
      <Text name="response_text" value="$response" />
      <Choices name="label" toName="response_text" choice="single" showInLine="true">
        <Choice value="Good Response"/>
        <Choice value="Bad Response"/>
      </Choices>
      <Header value="Model Confidence: $confidence"/>
      <Header value="Predicted Class: $predicted_class"/>
      <Header value="Corrected Class: $corrected_class"/>
    </View>
    """
    payload = {
        "title": PROJECT_NAME,
        "label_config": label_config
    }
    res = requests.post(f"{label_studio_url}/api/projects", headers=headers, json=payload)
    res.raise_for_status()
    project_id = res.json()["id"]
    context['ti'].xcom_push(key='project_id', value=project_id)


def send_tasks_to_label_studio(**context):
    all_responses = context['ti'].xcom_pull(key='all_responses', task_ids='sample_production_responses')
    project_id = context['ti'].xcom_pull(task_ids='create_label_studio_project', key='project_id')

    if not all_responses:
        return

    # Originally used for store images
    # public_ip = requests.get("http://169.254.169.254/latest/meta-data/public-ipv4").text.strip()
    # s3 = boto3.client(
    #     's3',
    #     endpoint_url=f"http://{public_ip}:9000",
    #     aws_access_key_id=os.environ['MINIO_USER'],
    #     aws_secret_access_key=os.environ['MINIO_PASSWORD'],
    #     region_name="us-east-1"
    # )

    label_studio_url = os.environ['LABEL_STUDIO_URL']
    token = os.environ['LABEL_STUDIO_USER_TOKEN']
    headers = {"Authorization": f"Token {token}"}

    tasks = []
    for item in all_responses:
        tasks.append({
            "data": {
                "response": item['response']
            },
            "meta": {"original_key": item['key']}
        })

    requests.post(
        f"{label_studio_url}/api/projects/{project_id}/import",
        json=tasks,
        headers=headers
    )


with DAG(
        dag_id='pipeline_1_get_and_label',
        default_args=default_args,
        description='Sample and tag production data for human review',
        start_date=datetime.today() - timedelta(days=1),
        schedule_interval="@daily",
        catchup=False,
) as dag:
    init_buckets = PythonOperator(
        task_id='init_buckets',
        python_callable=init_buckets_task
    )

    sample_production_responses_task = PythonOperator(
        task_id='sample_production_responses',
        python_callable=sample_production_responses
    )

    move_sampled_responses_task = PythonOperator(
        task_id='move_sampled_responses',
        python_callable=move_sampled_responses
    )

    create_project_task = PythonOperator(
        task_id='create_label_studio_project',
        python_callable=create_label_studio_project
    )

    label_studio_task = PythonOperator(
        task_id='send_tasks_to_label_studio',
        python_callable=send_tasks_to_label_studio
    )

    init_buckets >> sample_production_responses_task >> move_sampled_responses_task
    [move_sampled_responses_task, create_project_task] >> label_studio_task