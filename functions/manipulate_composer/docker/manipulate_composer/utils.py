import time
import slackweb
from .env import WEBHOOK_URL, PROJECT_ID

INTERVAL_MINUTES = 1


def wait_for_state(judge_state_fnc):
    while not judge_state_fnc():
        time.sleep(60 * INTERVAL_MINUTES)


def notify_slack(status):
    slack = slackweb.Slack(url=WEBHOOK_URL)
    attachments = [
        {
            "color": "#36a64f",
            "title": "Manipulate composer automatically",
            "fields": [{
                "title": "Project",
                "value": f"{PROJECT_ID}"
            }, {
                "title": "status",
                "value": status
            }],
        }
    ]
    slack.notify(attachments=attachments)
