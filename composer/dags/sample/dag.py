from airflow import DAG
from airflow.utils.dates import days_ago
from airflow.operators.dummy_operator import DummyOperator


default_args = {
    "start_date": days_ago(0),
}

with DAG(
        "sample",
        schedule_interval=None,
        catchup=False,
        default_args=default_args) as dag:

    DummyOperator(task_id="sample")

