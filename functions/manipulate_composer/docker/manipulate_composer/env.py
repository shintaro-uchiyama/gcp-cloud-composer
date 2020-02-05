import os

PROJECT_ID = os.environ.get("PROJECT_ID")
LOCATION = os.environ.get("LOCATION")
ZONE = os.environ.get("ZONE")
ENVIRONMENT_NAME = os.environ.get("ENVIRONMENT_NAME")
UPLOAD_TRIGGER_NAME = os.environ.get('UPLOAD_TRIGGER_NAME')
DAG_NAME_TO_RUN = os.environ.get('DAG_NAME_TO_RUN')
BRANCH_NAME = os.environ.get('BRANCH_NAME')
POLLING_INSTANCE_NAME = os.environ.get('POLLING_INSTANCE_NAME')
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
TARGET_LABEL = 'goog-composer-environment'
