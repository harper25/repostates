import os
from argparse import Namespace
from unittest.mock import MagicMock, call, patch

import pytest

from repostates import GitCommandsExecutor, GitRepo, create_arg_parser, get_repos

WORKING_DIR = os.getcwd()


def test_git_commands_executor_setup_processes():
    repos = [1, 2]
    git_command_mock = MagicMock()
    git_command_mock.setup_process.return_value = "mocked"
    git_commands_executor = GitCommandsExecutor()

    procs = git_commands_executor._setup_processes(repos, git_command_mock)

    assert procs == ["mocked", "mocked"]
    assert git_command_mock.setup_process.call_count == 2
    assert git_command_mock.setup_process.mock_calls == [call(1), call(2)]


def test_git_commands_executor_handle_processes():
    mocked_repo_1 = MagicMock(name="repo1")
    repos = [mocked_repo_1]
    git_command_mock = MagicMock()

    git_process = MagicMock()
    bytes_output = b"0 0\n"
    git_process.communicate.return_value = [bytes_output, b""]
    git_process.returncode = 0
    git_commands_executor = GitCommandsExecutor()

    git_commands_executor._handle_processes(repos, [git_process], git_command_mock)

    assert git_command_mock.handle_output.call_count == 1
    assert git_command_mock.handle_output.mock_calls == [
        call(mocked_repo_1, 0, "0 0", "")
    ]


def test_file_exists():
    with patch("os.path.exists", return_value=True):
        with patch("os.listdir", return_value=[".git"]):
            li = os.listdir()
            assert li == [".git"]
            assert os.path.exists(".git") is True


@pytest.mark.parametrize(
    "isdir,result",
    [
        (
            True,
            [
                GitRepo(fullpath="project_dir/backend_repo", name="backend_repo"),
                GitRepo(fullpath="project_dir/frontend_repo", name="frontend_repo"),
            ],
        ),
        (False, []),
    ],
)
def test_get_repos(isdir, result):
    with patch("repostates.os.path.isdir", return_value=isdir):
        with patch(
            "repostates.os.listdir", return_value=["backend_repo", "frontend_repo"]
        ):
            repos = get_repos(fullpath_start_dir="project_dir", regex=None)
            assert repos == result


@pytest.mark.parametrize(
    "input_args,result",
    [
        (
            [],
            Namespace(dir=WORKING_DIR, reg=None, verbose=0, command="status"),
        ),
        (
            ["--dir", "/root"],
            Namespace(dir="/root", reg=None, verbose=0, command="status"),
        ),
        (
            ["-vvv"],
            Namespace(dir=WORKING_DIR, reg=None, verbose=3, command="status"),
        ),
        (
            ["--reg", "designs|documentation"],
            Namespace(
                dir=WORKING_DIR, reg="designs|documentation", verbose=0, command="status"
            ),
        ),
        (
            ["--reg", "designs|documentation", "status"],
            Namespace(
                dir=WORKING_DIR, reg="designs|documentation", verbose=0, command="status"
            ),
        ),
        (
            ["pull"],
            Namespace(dir=WORKING_DIR, reg=None, verbose=0, command="pull"),
        ),
        (
            ["checkout", "development"],
            Namespace(
                dir=WORKING_DIR,
                reg=None,
                verbose=0,
                command="checkout",
                target_branch="development",
            ),
        ),
        (
            ["gone-branches"],
            Namespace(
                dir=WORKING_DIR,
                reg=None,
                verbose=0,
                command="gone-branches",
                subcommand="list",
            ),
        ),
    ],
)
def test_create_arg_parser(input_args, result):
    parser = create_arg_parser()
    args = parser.parse_args(input_args)
    assert args == result
