# -*- coding: utf-8 -*-
import dataclasses
import pathlib
import sys

from codecov import github_client, log, settings

GITHUB_ACTIONS_LOGIN = 'CI-codecov[bot]'


class CannotDeterminePR(Exception):
    pass


class CannotPostComment(Exception):
    pass


class CannotGetPullRequest(Exception):
    pass


class NoArtifact(Exception):
    pass


@dataclasses.dataclass
class RepositoryInfo:
    default_branch: str
    visibility: str

    def is_default_branch(self, ref: str) -> bool:
        return f'refs/heads/{self.default_branch}' == ref

    def is_public(self) -> bool:
        return self.visibility == 'public'


def get_repository_info(github: github_client.GitHub, repository: str) -> RepositoryInfo:
    response = github.repos(repository).get()

    return RepositoryInfo(default_branch=response.default_branch, visibility=response.visibility)


def get_my_login(github: github_client.GitHub) -> str:
    try:
        response = github.user.get()
    except github_client.Forbidden:
        # The GitHub actions user cannot access its own details
        # and I'm not sure there's a way to see that we're using
        # the GitHub actions user except noting that it fails
        return GITHUB_ACTIONS_LOGIN

    return response.login


def get_pr_number(github: github_client.GitHub, config: settings.Config) -> int:
    if config.GITHUB_PR_NUMBER:
        try:
            pull_request = github.repos(config.GITHUB_REPOSITORY).pulls(config.GITHUB_PR_NUMBER).get()
            if pull_request.state != 'open':
                raise github_client.NotFound

            return pull_request.number
        except github_client.Forbidden as exc:
            raise CannotGetPullRequest from exc
        except github_client.NotFound:
            log.warning(f'Pull request #{config.GITHUB_PR_NUMBER} does not exist')

    # If we're not on a PR, we need to find the PR number from the branch name
    if config.GITHUB_REF:
        try:
            pull_requests = github.repos(config.GITHUB_REPOSITORY).pulls.get(state='open', head=config.GITHUB_REF)
            if len(pull_requests) != 1:
                raise github_client.NotFound

            return pull_requests[0].number
        except github_client.Forbidden as exc:
            raise CannotGetPullRequest from exc
        except github_client.NotFound as exc:
            raise CannotGetPullRequest from exc

    raise CannotGetPullRequest(
        'This worflow is not triggered on a pull_request event, '
        "nor on a push event on a branch. Consequently, there's nothing to do. "
        'Exiting.'
    )


def get_pr_diff(  # pylint: disable=too-many-arguments
    github: github_client.GitHub,
    repository: str,
    pr_number: int,
) -> None:
    try:
        pull_request = github.repos(repository).pulls(pr_number).get()
        if pull_request.state != 'open':
            raise github_client.NotFound
    except github_client.Forbidden as exc:
        raise CannotGetPullRequest from exc
    except github_client.NotFound:
        log.warning(f'Pull request #{pr_number} does not exist')


def post_comment(  # pylint: disable=too-many-arguments
    github: github_client.GitHub,
    me: str,
    repository: str,
    pr_number: int,
    contents: str,
    marker: str,
) -> None:
    if len(contents) > 65536:
        raise CannotPostComment('Comment exceeds allowed size(65536)')

    issue_comments_path = github.repos(repository).issues(pr_number).comments
    comments_path = github.repos(repository).issues.comments

    for comment in issue_comments_path.get():
        if comment.user.login == me and marker in comment.body:
            log.info('Update previous comment')
            try:
                comments_path(comment.id).patch(body=contents)
            except github_client.Forbidden as exc:
                raise CannotPostComment from exc
            except github_client.ApiError as exc:
                raise CannotPostComment from exc
            break
    else:
        log.info('Adding new comment')
        try:
            issue_comments_path.post(body=contents)
        except github_client.Forbidden as exc:
            raise CannotPostComment from exc


def escape_property(s: str) -> str:
    return s.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A').replace(':', '%3A').replace(',', '%2C')


def escape_data(s: str) -> str:
    return s.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')


def get_workflow_command(command: str, command_value: str, **kwargs: str) -> str:
    """
    Returns a string that can be printed to send a workflow command
    https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions
    """
    values_listed = [f'{key}={escape_property(value)}' for key, value in kwargs.items()]

    context = f" {','.join(values_listed)}" if values_listed else ''
    return f'::{command}{context}::{escape_data(command_value)}'


def send_workflow_command(command: str, command_value: str, **kwargs: str) -> None:
    print(
        get_workflow_command(command=command, command_value=command_value, **kwargs),
        file=sys.stderr,
    )


def create_missing_coverage_annotations(annotation_type: str, annotations: list[tuple[pathlib.Path, int, int]]):
    """
    Create annotations for lines with missing coverage.

    annotation_type: The type of annotation to create. Can be either "error" or "warning".
    annotations: A list of tuples of the form (file, line_start, line_end)
    """
    send_workflow_command(command='group', command_value='Annotations of lines with missing coverage')
    for file, line_start, line_end in annotations:
        if line_start == line_end:
            message = f'Missing coverage on line {line_start}'
        else:
            message = f'Missing coverage on lines {line_start}-{line_end}'

        send_workflow_command(
            command=annotation_type,
            command_value=message,
            # This will produce \ paths when running on windows.
            # GHA doc is unclear whether this is right or not.
            file=str(file),
            line=str(line_start),
            endLine=str(line_end),
            title='Missing coverage',
        )
    send_workflow_command(command='endgroup', command_value='')
