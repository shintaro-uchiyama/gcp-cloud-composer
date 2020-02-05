import googleapiclient.discovery
from .env import PROJECT_ID, ZONE, POLLING_INSTANCE_NAME


def delete_polling_instance():
    compute = googleapiclient.discovery.build('compute', 'v1')
    result = compute.instances().list(project=PROJECT_ID, zone=ZONE).execute()
    instance_id = ''
    for instance in result['items']:
        if instance['name'] == POLLING_INSTANCE_NAME:
            instance_id = instance['id']

    if instance_id != '':
        compute.instances().delete(
            project=PROJECT_ID,
            zone=ZONE,
            instance=instance_id).execute()
