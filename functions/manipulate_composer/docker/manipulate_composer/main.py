import sys
import google.auth
import google.cloud.logging
from .composer import Composer
from .compute_engine import delete_polling_instance
from .utils import wait_for_state, notify_slack
from .env import ENVIRONMENT_NAME, DAG_NAME_TO_RUN
from timeout_decorator import timeout, TimeoutError

MAXIMUM_HOURS = 3


@timeout(60 * 60 * MAXIMUM_HOURS)
def _create_composer():
    if Composer.environment_exists(ENVIRONMENT_NAME):
        raise Exception('Composer Already exists!')

    # Composer作成
    composer = Composer(ENVIRONMENT_NAME)
    notify_slack('create composer')

    # Composer PyPI更新
    wait_for_state(composer.update_pypi)
    notify_slack('update composer PyPI')

    # Upload Airflow dag
    wait_for_state(composer.upload_airflow_dags)
    notify_slack('upload dags')


@timeout(60 * 60 * MAXIMUM_HOURS)
def _delete_composer():
    if not Composer.environment_exists(ENVIRONMENT_NAME):
        raise Exception('Composer does not exists!')

    # Composer取得
    composer = Composer(ENVIRONMENT_NAME)

    # Composer削除
    wait_for_state(composer.delete)
    notify_slack('delete composer')

    # Composer紐付きDisk削除
    wait_for_state(composer.delete_disk)
    notify_slack('delete Composer disk not in use')


@timeout(60 * 60 * MAXIMUM_HOURS)
def _run_composer_once():
    _create_composer()

    # Run Airflow dag
    composer = Composer(ENVIRONMENT_NAME)
    wait_for_state(lambda: composer.run_airflow_dag(DAG_NAME_TO_RUN))
    notify_slack('run dag')

    _delete_composer()


def main():
    try:
        client = google.cloud.logging.Client()
        client.setup_logging()

        manipulate_type = sys.argv[1]
        if manipulate_type == 'create':
            _create_composer()
        elif manipulate_type == 'delete':
            _delete_composer()
        if manipulate_type == 'run_once':
            _run_composer_once()
    except TimeoutError:
        notify_slack('one time composer operation timeout!')
    except Exception as e:
        notify_slack(e.message)
    finally:
        # Polling GCE削除
        delete_polling_instance()
        notify_slack('delete polling instance')


if __name__ == '__main__':
    main()
