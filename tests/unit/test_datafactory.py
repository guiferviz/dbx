import datetime as dt
import json
import pathlib
import unittest
from unittest.mock import patch

from mlflow import ActiveRun
from mlflow.entities import Experiment
from mlflow.entities.run import Run, RunInfo, RunData

from dbx.commands.configure import configure
from dbx.commands.datafactory import deploy as datafactory_deploy
from dbx.commands.deploy import deploy, _update_job  # noqa
from dbx.utils.common import DEFAULT_DEPLOYMENT_FILE_PATH
from .utils import DbxTest, invoke_cli_runner, test_dbx_config

run_info = RunInfo(
    run_uuid="1",
    experiment_id="1",
    user_id="dbx",
    status="STATUS",
    start_time=dt.datetime.now(),
    end_time=dt.datetime.now(),
    lifecycle_stage="STAGE",
    artifact_uri="dbfs:/Shared/dbx-testing"
)
run_data = RunData()
run_mock = ActiveRun(Run(run_info, run_data))


class DatafactoryDeployTest(DbxTest):

    @patch("databricks_cli.sdk.api_client.ApiClient.perform_query", return_value=None)
    @patch(
        "databricks_cli.sdk.service.DbfsService.get_status", return_value=None
    )
    @patch(
        "databricks_cli.configure.provider.ProfileConfigProvider.get_config",
        return_value=test_dbx_config,
    )
    @patch("databricks_cli.workspace.api.WorkspaceService.mkdirs", return_value=True)
    @patch(
        "databricks_cli.workspace.api.WorkspaceService.get_status", return_value=True
    )
    @patch("databricks_cli.jobs.api.JobsService.list_jobs", return_value={"jobs": []})
    @patch("databricks_cli.jobs.api.JobsApi.create_job", return_value={"job_id": "1"})
    @patch(
        "mlflow.get_experiment_by_name",
        return_value=Experiment("id", None, "location", "dbfs:/Shared/dbx/test", None),
    )
    @patch("mlflow.set_experiment", return_value=None)
    @patch("mlflow.start_run", return_value=run_mock)
    @patch("mlflow.log_artifact", return_value=None)
    @patch("mlflow.set_tags", return_value=None)
    @patch("dbx.commands.datafactory.DatafactoryDeployer", autospec=True)
    def test_datafactory_deploy(self, *_):
        with self.project_dir:
            ws_dir = "/Shared/dbx/projects/%s" % self.project_name
            configure_result = invoke_cli_runner(
                configure,
                [
                    "--environment",
                    "default",
                    "--profile",
                    self.profile_name,
                    "--workspace-dir",
                    ws_dir,
                ],
            )
            self.assertEqual(configure_result.exit_code, 0)

            deployment_file = pathlib.Path(DEFAULT_DEPLOYMENT_FILE_PATH)
            deploy_content = json.loads(deployment_file.read_text())

            sample_job = deploy_content.get("default").get("jobs")[0]

            sample_job["permissions"] = {
                "access_control_list": [
                    {
                        "user_name": "some_user@example.com",
                        "permission_level": "IS_OWNER",
                    },
                    {
                        "group_name": "some-user-group",
                        "permission_level": "CAN_VIEW"
                    }
                ]
            }

            deployment_file.write_text(json.dumps(deploy_content, indent=4))

            deploy_result = invoke_cli_runner(
                deploy,
                [
                    "--environment", "default",
                    "--write-specs-to-file", ".dbx/deployment-result.json"
                ]
            )

            self.assertEqual(deploy_result.exit_code, 0)

            datafactory_deploy_result = invoke_cli_runner(
                datafactory_deploy,
                [
                    "--environment", "default",
                    "--specs-file", ".dbx/deployment-result.json",
                    "--subscription-name", "some-subscription",
                    "--resource-group", "some-resource-group",
                    "--factory-name", "some-factory",
                    "--name", "some-pipeline"
                ]
            )

            self.assertEqual(datafactory_deploy_result.exit_code, 0)


if __name__ == "__main__":
    unittest.main()
