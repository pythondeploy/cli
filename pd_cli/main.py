"""Entrypoint to the Python Deploy CLI."""
import typer

from .build import build_command
from .deploy import deploy_command
from .run import run_command

app = typer.Typer()
app.command("deploy")(deploy_command)
app.command("run")(run_command)
app.command("build")(build_command)
