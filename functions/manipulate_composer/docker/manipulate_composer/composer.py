import json
import requests
import six.moves.urllib.parse
import google.auth
from google.cloud import storage
from google.auth.transport.requests import AuthorizedSession
import googleapiclient.discovery
from .env import PROJECT_ID, LOCATION, ZONE, TARGET_LABEL, UPLOAD_TRIGGER_NAME, WEBHOOK_URL
from .utils import wait_for_state
from .cloud_build import CloudBuild


class Composer:
    def __init__(self, environment_name):
        self.environment_name = environment_name
        self.environments_url \
            = f"https://composer.googleapis.com/v1beta1/projects/{PROJECT_ID}/locations/{LOCATION}/environments"
        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        self.authed_session = AuthorizedSession(credentials)

        if not self._exists():
            request_body = {
                "name": f"projects/{PROJECT_ID}/locations/{LOCATION}/environments/{self.environment_name}",
                "config": {
                    "nodeCount": 3,
                    "softwareConfig": {
                        "imageVersion": "composer-1.8.3-airflow-1.10.2",
                        "pythonVersion": "3",
                        "envVariables": {
                            "PROJECT_ID": PROJECT_ID,
                            "WEBHOOK_URL": WEBHOOK_URL
                        }
                    },
                    "nodeConfig": {
                        "location": f"projects/{PROJECT_ID}/zones/{ZONE}",
                        "machineType": f"projects/{PROJECT_ID}/zones/{ZONE}/machineTypes/n1-standard-4",
                        "network": f"projects/{PROJECT_ID}/global/networks/default",
                        "diskSizeGb": 100,
                        "oauthScopes": [
                            "https://www.googleapis.com/auth/cloud-platform"
                        ]
                    }
                }
            }
            self.authed_session.request("POST", self.environments_url,
                                        json.dumps(request_body), {"Content-Type": "application/json"})
            # Composer作成完了待ち
            wait_for_state(self._exists)

        self.environment_url = f"{self.environments_url}/{self.environment_name}/"
        self._fetch_latest_environment()

    def _exists(self):
        composer_environments = self.authed_session.request("GET", self.environments_url)
        composer_environments_json = composer_environments.json()
        if "environments" in composer_environments_json:
            for environment in composer_environments_json["environments"]:
                if self.environment_name in environment["name"]:
                    return True
        return False

    def update_pypi(self):
        if not self._is_running():
            return False

        update_environment_url = self.environment_url + "?updateMask=config.softwareConfig.pypiPackages"
        request_body = {
            "config": {
                "softwareConfig": {
                    "pypiPackages": {
                        "slackweb": "==1.0.5"
                    }
                }
            }
        }
        self.authed_session.request("PATCH", update_environment_url,
                                    json.dumps(request_body), {"Content-Type": "application/json"})
        return True

    def _is_running(self):
        self._fetch_latest_environment()
        return True if self.environment["state"] == 'RUNNING' else False

    def _fetch_latest_environment(self):
        response = self.authed_session.request("GET", self.environment_url)
        self.environment = response.json()

    def _pypi_exists(self):
        self._fetch_latest_environment()
        return True if self.environment["state"] == "RUNNING" \
                       and "pypiPackages" in self.environment["config"]["softwareConfig"] else False

    def upload_airflow_dags(self):
        if self._pypi_exists():
            upload_dag_cloud_build = CloudBuild(UPLOAD_TRIGGER_NAME)
            upload_dag_cloud_build.run_trigger()
            return True
        return False

    def run_airflow_dag(self, dag_name):
        upload_dag_cloud_build = CloudBuild(UPLOAD_TRIGGER_NAME)
        if upload_dag_cloud_build.latest_build_success():
            token = self._get_token()
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }

            r = requests.post(f"{self.environment['config']['airflowUri']}/api/experimental/dags/{dag_name}/dag_runs",
                              data=json.dumps({}, ensure_ascii=False).encode('utf-8'), headers=headers)
            r.raise_for_status()
            return True
        return False

    def _get_token(self):
        # composerにアクセスするCLIENT_IDの取得
        redirect_response = requests.get(self.environment['config']['airflowUri'], allow_redirects=False)
        redirect_location = redirect_response.headers['location']
        parsed = six.moves.urllib.parse.urlparse(redirect_location)
        query_string = six.moves.urllib.parse.parse_qs(parsed.query)
        client_id = query_string['client_id'][0]

        # composerにアクセスするアクセストークンの取得
        service_account = 'default'
        metadata_url = 'http://metadata.google.internal/computeMetadata/v1'
        url = f'{metadata_url}/instance/service-accounts/{service_account}/identity'
        params = {
            'audience': client_id,
            'format': 'full'
        }
        r = requests.get(url, headers={'Metadata-Flavor': 'Google'}, params=params)
        r.raise_for_status()
        return r.text

    def _get_latest_dag_runs(self):
        token = self._get_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        r = requests.get(f"{self.environment['config']['airflowUri']}/api/experimental/latest_runs", headers=headers)
        r.raise_for_status()
        return r.json()

    def delete(self):
        if self._running_dag_exists():
            return False

        self.authed_session.request("DELETE", self.environment_url)
        self._delete_cloud_storage()
        return True

    def _running_dag_exists(self):
        token = self._get_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        for dag in self._get_latest_dag_runs()['items']:
            if dag['dag_id'] != 'airflow_monitoring':
                r = requests.get(
                    f"{self.environment['config']['airflowUri']}/api/experimental/dags/{dag['dag_id']}/dag_runs",
                    headers=headers)
                r.raise_for_status()
                if r.json()[0]['state'] == 'running':
                    return True
        return False

    def _delete_cloud_storage(self):
        storage_client = storage.Client(project=PROJECT_ID)
        buckets = storage_client.list_buckets()
        for bucket in buckets:
            if TARGET_LABEL in bucket.labels and bucket.labels[TARGET_LABEL] == self.environment_name:
                target_bucket = storage_client.get_bucket(bucket.name)
                target_bucket.delete_blobs(target_bucket.list_blobs())
                target_bucket.delete(True)

    def delete_disk(self):
        if self._exists():
            return False

        composer_disk_not_in_use = self._get_disk_not_in_use()
        if composer_disk_not_in_use != "":
            compute = googleapiclient.discovery.build("compute", "v1", cache_discovery=False)
            compute.disks().delete(
                project=PROJECT_ID,
                zone=ZONE,
                disk=composer_disk_not_in_use
            ).execute()
        return True

    def _get_disk_not_in_use(self):
        disks_info = googleapiclient.discovery.build("compute", "v1", cache_discovery=False) \
            .disks().list(project=PROJECT_ID, zone=ZONE).execute()

        for disk in disks_info["items"]:
            if "labels" in disk \
                    and TARGET_LABEL in disk["labels"] \
                    and disk["labels"][TARGET_LABEL] == self.environment_name \
                    and "users" not in disk:
                return disk["name"]
        return ""

    @staticmethod
    def environment_exists(environment_name):
        environments_url \
            = f"https://composer.googleapis.com/v1beta1/projects/{PROJECT_ID}/locations/{LOCATION}/environments"
        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        authed_session = AuthorizedSession(credentials)
        composer_environments = authed_session.request("GET", environments_url)
        composer_environments_json = composer_environments.json()
        if "environments" in composer_environments_json:
            for environment in composer_environments_json["environments"]:
                if environment_name in environment["name"]:
                    return True
        return False
