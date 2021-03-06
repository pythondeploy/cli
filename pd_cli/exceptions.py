"""Define exceptions for PD CLI package."""


class CloudFormationTransformationFailed(Exception):
    """The changes to CloudFormation failed to apply."""


class DockerBuildFailed(Exception):
    """Building the docker image failed."""


class ECRPushFailed(Exception):
    """Pushing the image to ECR failed."""


class LambdaInvocationFailed(Exception):
    """The invokation of the Lambda function failed."""


class ShellCommandFailed(Exception):
    """The invoked shell command failed."""


class UnexpectedResponse(Exception):
    """The response from the LambdaFunction has an unknown format."""
