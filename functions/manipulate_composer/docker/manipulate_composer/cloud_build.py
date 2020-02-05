import json
import google.auth
from google.auth.transport.requests import AuthorizedSession
from .env import PROJECT_ID, BRANCH_NAME


class CloudBuild:
    def __init__(self, trigger_name):
        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        self.authed_session = AuthorizedSession(credentials)
        cloud_build_triggers_url = f"https://cloudbuild.googleapis.com/v1/projects/{PROJECT_ID}/triggers"
        cloud_build_triggers = self.authed_session.request("GET", cloud_build_triggers_url)
        self.cloud_build_trigger_id = ""
        for cloud_build_trigger in cloud_build_triggers.json()["triggers"]:
            if cloud_build_trigger["name"] == trigger_name:
                self.cloud_build_trigger_id = cloud_build_trigger["id"]

    def run_trigger(self):
        cloud_build_trigger_url \
            = f"https://cloudbuild.googleapis.com/v1/projects/{PROJECT_ID}/triggers/{self.cloud_build_trigger_id}:run"
        request_body = {
            "branchName": BRANCH_NAME
        }
        self.authed_session.request("POST", cloud_build_trigger_url,
                                    json.dumps(request_body), {"Content-Type": "application/json"})

    def latest_build_success(self):
        cloud_builds_url = f"https://cloudbuild.googleapis.com/v1/projects/{PROJECT_ID}/builds"
        cloud_builds = self.authed_session.request("GET", cloud_builds_url)
        for cloud_build in cloud_builds.json()['builds']:
            if cloud_build['buildTriggerId'] == self.cloud_build_trigger_id:
                return True if cloud_build['status'] == 'SUCCESS' else False
        return False
