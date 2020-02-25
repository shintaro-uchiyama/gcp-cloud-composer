import os
import base64
import googleapiclient.discovery

PROJECT_ID = os.environ.get('GCP_PROJECT')
LOCATION = os.environ.get('LOCATION')
ZONE = os.environ.get('ZONE')
ENVIRONMENT_NAME = os.environ.get('ENVIRONMENT_NAME')
UPLOAD_TRIGGER_NAME = os.environ.get('UPLOAD_TRIGGER_NAME')
DAG_NAME_TO_RUN = os.environ.get('DAG_NAME_TO_RUN')
BRANCH_NAME = os.environ.get('BRANCH_NAME')
POLLING_INSTANCE_NAME = os.environ.get('POLLING_INSTANCE_NAME')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')


def manipulate_composer(event, context):
    manipulate_type = base64.b64decode(event["data"]).decode("utf-8")
    _create_polling_instance(manipulate_type)


def _create_polling_instance(manipulate_type):
    compute = googleapiclient.discovery.build('compute', 'v1', cache_discovery=False)
    image_response = compute.images().getFromFamily(
        project='cos-cloud', family='cos-stable').execute()

    config = {
        'name': POLLING_INSTANCE_NAME,
        'machineType': f"zones/{ZONE}/machineTypes/f1-micro",
        'disks': [
            {
                'boot': True,
                'autoDelete': True,
                'initializeParams': {
                    'sourceImage': image_response['selfLink'],
                }
            }
        ],
        'networkInterfaces': [{
            'network': 'global/networks/default',
            'accessConfigs': [
                {'type': 'ONE_TO_ONE_NAT', 'name': 'External NAT'}
            ]
        }],
        'canIpForward': False,
        'displayDevice': {
            "enableDisplay": False
        },
        'labels': {
            "container-vm": image_response['name']
        },
        'serviceAccounts': [{
            'email': 'default',
            'scopes': [
                'https://www.googleapis.com/auth/cloud-platform'
            ]
        }],
        'metadata': {
            'items': [{
                'key': 'gce-container-declaration',
                'value': 'spec: \n'
                         '  containers:\n'
                         '    - name: test\n'
                         '      args:\n'
                         f"        - {manipulate_type}\n"
                         f"      image: asia.gcr.io/{PROJECT_ID}/manipulate-composer\n"
                         '      env:\n'
                         '        - name: PROJECT_ID\n'
                         f"          value: {PROJECT_ID}\n"
                         '        - name: LOCATION\n'
                         f"          value: {LOCATION}\n"
                         '        - name: ZONE\n'
                         f"          value: {ZONE}\n"
                         '        - name: ENVIRONMENT_NAME\n'
                         f"          value: {ENVIRONMENT_NAME}\n"
                         '        - name: UPLOAD_TRIGGER_NAME\n'
                         f"          value: {UPLOAD_TRIGGER_NAME}\n"
                         '        - name: DAG_NAME_TO_RUN\n'
                         f"          value: {DAG_NAME_TO_RUN}\n"
                         '        - name: BRANCH_NAME\n'
                         f"          value: {BRANCH_NAME}\n"
                         '        - name: WEBHOOK_URL\n'
                         f"          value: {WEBHOOK_URL}\n"
                         '        - name: POLLING_INSTANCE_NAME\n'
                         f"          value: {POLLING_INSTANCE_NAME}\n"
                         '      stdin: false\n'
                         '      tty: false\n'
                         '  restartPolicy: Never'
            }, {
                "key": "google-logging-enabled",
                "value": "true"
            }]
        }
    }

    return compute.instances().insert(
        project=PROJECT_ID,
        zone=ZONE,
        body=config).execute()
