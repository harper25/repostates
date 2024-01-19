import os
from unittest.mock import MagicMock, call, patch

import pytest

from repostates import GitCommandsExecutor, GitRepo, get_repos


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
    repos = ["repo1"]
    git_command_mock = MagicMock()
    git_process = MagicMock()
    bytes_output = b"0 0\n"
    git_process.communicate.return_value = [bytes_output, b""]
    git_process.returncode = 0
    git_commands_executor = GitCommandsExecutor()

    git_commands_executor._handle_processes(repos, [git_process], git_command_mock)

    assert git_command_mock.handle_output.call_count == 1
    assert git_command_mock.handle_output.mock_calls == [call("repo1", 0, "0 0", "")]


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
