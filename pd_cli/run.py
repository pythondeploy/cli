"""CLI command to run shell commands on a Lambda Function."""
import json
import os
import subprocess
from pprint import pformat
from typing import Any, Dict, List, Optional

import typer
from boto3 import Session

from .exceptions import LambdaInvocationFailed, ShellCommandFailed, UnexpectedResponse
from .helpers import get_aws_account_information


def run_fargate_shell(
    aws_account: Dict[str, Any], shell_args: Optional[List[str]]
) -> None:
    """
    Run a shell command in an ECS container through aws ecs exec-command.

    `stdout` and and `stderr` from the ran command are printed locally
    to stdout. The output comes from the AWS CLI `exec-command`.

    A `ShellCommandFailed` exception is raised if it is not possible
    to execute the command.

    The return code of the command is not captured. The output needs to
    be parsed in order to detect if the command executed properly or not.
    """

    ecs_client = Session(
        aws_access_key_id=aws_account["credentials"]["aws_access_key_id"],
        aws_secret_access_key=aws_account["credentials"]["aws_secret_access_key"],
        aws_session_token=aws_account["credentials"]["aws_session_token"],
        region_name=aws_account["credentials"]["region_name"],
    ).client("ecs")
    task_arn = ecs_client.list_tasks(
        cluster=aws_account["ecs_cluster"],
        serviceName=aws_account["worker_service"] or aws_account["web_service"],
    )["taskArns"][0]

    process = subprocess.Popen(
        [
            "aws",
            "ecs",
            "execute-command",
            "--cluster",
            aws_account["ecs_cluster"],
            "--task",
            task_arn,
            "--container",
            "WebContainer",
            "--interactive",
            "--command",
            " ".join(shell_args),
        ],
        env={
            **os.environ,
            **{
                "AWS_ACCESS_KEY_ID": aws_account["credentials"]["aws_access_key_id"],
                "AWS_SECRET_ACCESS_KEY": aws_account["credentials"][
                    "aws_secret_access_key"
                ],
                "AWS_SESSION_TOKEN": aws_account["credentials"]["aws_session_token"],
                "AWS_REGION": aws_account["credentials"]["region_name"],
            },
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    success = True
    for line in iter(lambda: process.stdout.readline(), b""):
        if b"----------ERROR-------" in line:
            success = False
        typer.echo(line.rstrip())

    if not success:
        raise ShellCommandFailed("Shell command failed")


def run_lambda_shell(
    aws_account: Dict[str, Any], shell_args: Optional[List[str]], log_result: bool
) -> None:
    """
    Run a shell command in the Tasks lambda function.

    `stdout` and and `stderr` from the ran command are printed locally
    in their corresponding stream.

    The python process exits with the same return code from the command.

    If the lambda function fails to execute or it is not possible to execute
    the shell command, an exception is raised.
    """
    lambda_client = Session(
        aws_access_key_id=aws_account["credentials"]["aws_access_key_id"],
        aws_secret_access_key=aws_account["credentials"]["aws_secret_access_key"],
        aws_session_token=aws_account["credentials"]["aws_session_token"],
        region_name=aws_account["credentials"]["region_name"],
    ).client("lambda")

    payload = {
        "args": shell_args,
        "log_result": log_result,
        "handler_path": "pd_aws_lambda.handlers.shell.handler",
    }

    typer.echo("Invoking Lambda function")
    response = lambda_client.invoke(
        FunctionName=aws_account["tasks_function"],
        Payload=json.dumps(payload).encode(),
    )

    if response["StatusCode"] != 200:
        raise LambdaInvocationFailed(
            "Lambda execution failed", response.get("FunctionError")
        )

    result = json.loads(response["Payload"].read().decode())

    if not isinstance(result, dict):
        raise UnexpectedResponse(result)

    if "FunctionError" in response:
        typer.echo(pformat(result["errorMessage"]), err=True)
        raise ShellCommandFailed("Shell command failed", result["errorType"])

    if result["stdout"]:
        typer.echo(result["stdout"].strip("\n"))

    if result["stderr"]:
        typer.echo(result["stderr"].strip("\n"), err=True)

    exit(result["returncode"])


def run_command(
    shell_args: Optional[List[str]] = typer.Argument(None, help="Command to execute."),
    log_result: bool = typer.Option(
        False,
        help="Log the results into AWS CloudWatch. (Only for Lambda applications)",
    ),
    app_id: str = typer.Option(
        os.environ.get("PD_APP_ID"),
        help="PythonDeploy application id. Default: environment variable PD_APP_ID",
    ),
    api_key: str = typer.Option(
        os.environ.get("PD_API_KEY"),
        help="PythonDeploy api key. Default: environment variable PD_API_KEY",
    ),
) -> None:
    """
    Execute a remote commands in your application.

    ---

    For Fargate applications, run a shell command in an ECS container through
    `aws ecs exec-command`.

    `stdout` and and `stderr` from the ran command are printed locally
    to stdout. The output comes from the AWS CLI `exec-command`.

    A `ShellCommandFailed` exception is raised if it is not possible
    to execute the command.

    The return code of the command is not captured. The output needs to
    be parsed in order to detect if the command executed properly or not.

    ---

    For Lambda applications, run a shell command in the Tasks lambda function.

    `stdout` and and `stderr` from the ran command are printed locally
    in their corresponding stream.

    The python process exits with the same return code from the command.

    If the lambda function fails to execute or it is not possible to execute
    the shell command, an exception is raised.


    """
    aws_account = get_aws_account_information(app_id, api_key)
    if aws_account["manager"] == "LambdaFunctionManager":
        run_lambda_shell(aws_account, shell_args, log_result)
        return

    if aws_account["manager"] == "FargateFunctionManager":
        run_fargate_shell(aws_account, shell_args)
        return
