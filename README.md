# 概要
Composerに関して以下3つの操作を実行するCloud Functions  

- Composer作成
- Composer削除
- Composer一度だけ作成&実行

具体的には以下用途を想定

## 営業時間だけComposer起動
Cloud Schedulerにて朝：Composer作成job, 夕方：Composer削除jobを作成することで実現  

## 月に1回Airflowを実行
GitHubの特定ブランチdagを一度だけ実行することを想定  
Composerの作成->実行->削除まで行っているため、完了までに1-2時間近くかかる

# デプロイ
基本的にシェルスクリプトのprojectに自身のプロジェクトIDを指定して実行が必要
## Dockerのデプロイ
Composerの作成完了待ちなどの用途でPolling Container on GCEを作成している  
GCE上で動かすDocker imageをContainer Registerにデプロイ
```bash
project=[project_name]
cd functions/manipulate_composer/docker
docker build -t manipulate-composer .
docker tag manipulate-composer:latest asia.gcr.io/${project}/manipulate-composer:latest
docker push asia.gcr.io/${project}/manipulate-composer
```

## Cloud buildのデプロイ
最新dagをアップロードするためのCloud Build Trigger作成  
コンソールにてリポジトリを接続し  
trigger_config.yamlにて以下の通り設定の上、コマンド実行  
- owner：接続させたい自身のGitHub owner
- name：接続させたい自身のGitHub name
  - 例）https://github.com/[owner]/[name]
- _PROJECT_ID：自身のプロジェクト名
- _COMPSER_ENV：作成したいComposer名
```bash
gcloud beta builds triggers create github \
    --trigger-config="build/upload_dags_to_airflow/trigger_config.yaml"
```

## cloud functionsのデプロイ
`--env-vars-file`に以下の通り対象のプロジェクト情報を指定してデプロイ  
- ENVIRONMENT_NAME：作成したいComposer名
- WEBHOOK_URL：操作状況をSlackに通知するためのwebhook url
  - 以下URLからwebhook URLを作成し設定
  - https://slack.com/services/new/incoming-webhook
- DAG_NAME_TO_RUN：Dummyで作成したDAG IDのsampleを指定
- BRANCH_NAME：DAGを反映させたいGitHub branch。master指定
```bash
project=[project_name]
gcloud functions deploy manipulate_composer \
  --runtime python37 \
  --trigger-topic manipulate_composer \
  --source functions/manipulate_composer \
  --project ${project} \
  --region asia-northeast1 \
  --env-vars-file functions/manipulate_composer/.env.yaml
```

## Cloud Schedulerのデプロイ
### 営業時間にComposer起動
朝作成スケジューラー
```bash
project=[project_name]
gcloud beta scheduler jobs create pubsub create_composer \
    --project ${project} \
    --time-zone='Asia/Tokyo' \
    --schedule='0 7 * * 1-5' \
    --topic=manipulate_composer \
    --message-body='create'
```

夜削除スケジューラー
```bash
project=[project_name]
gcloud beta scheduler jobs create pubsub delete_composer \
    --project ${project} \
    --time-zone='Asia/Tokyo' \
    --schedule='0 19 * * 1-5' \
    --topic=manipulate_composer \
    --message-body='delete'
```

### 月に1回Airflowを実行
毎月1日の10:00にAirflowを実行するScheduler
```bash
project=[project_name]
schedule="0 10 1 * *"
gcloud beta scheduler jobs create pubsub run_composer_once \
    --project ${project} \
    --time-zone='Asia/Tokyo' \
    --schedule=${schedule} \
    --topic=manipulate_composer \
    --message-body='run_once'
```
