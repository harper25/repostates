import argparse
import os
import re
import subprocess
import sys
from abc import ABC, abstractmethod
from enum import Enum


def main():
    fullpath_start_dir, regex = get_cli_arguments()
    repos = get_repos(fullpath_start_dir, regex)

    if not repos:
        print(f"{Style.YELLOW}No repos found!{Style.RESET}")
        return

    git_command_executor = GitCommandsExecutor()
    pipeline = [GitCurrentBranch(), GitFetchOrigin(), GitUpstreamBranch(), GitCommitsState()]

    for git_command in pipeline:
        if git_command.message:
            print(git_command.message)
        git_command_executor.run_processes(repos, git_command)

    present_table_summary(repos)


def present_table_summary(repos):
    header_name = "REPOSITORY"
    header_branch = "BRANCH"

    def get_column_width(header, content, margin=3):
        max_width_content = max(len(row) for row in content)
        column_width = max(len(header), max_width_content) + margin
        return column_width

    repo_names = [repo.name for repo in repos]
    branch_names = [repo.current_branch for repo in repos]
    col_width_name = get_column_width(header_name, repo_names)
    col_width_branch = get_column_width(header_branch, branch_names)

    print(
        f"\n{Style.BLUE}{header_name:<{col_width_name}}{header_branch:<{col_width_branch}}COMMITS{Style.RESET}"
    )
    print(
        f"{Style.BLUE}{Style.UNDERLINE}{'':<{col_width_name}}{'':<{col_width_branch}}AHEAD/BEHIND{Style.RESET}"
    )
    for repo in sorted(repos, key=lambda repo: repo.name):
        print(
            f"{STATUS_COLOR_MAPPING[repo.status]}{repo.name:<{col_width_name}}"
            f"{repo.current_branch:<{col_width_branch}}"
            f"{repo.commits_ahead:<4}"
            f"{repo.commits_behind}{Style.RESET}"
        )


def get_cli_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "dir",
        nargs="?",
        help="directory with your git repositories, defaults to the current directory",
        default=os.getcwd(),
    )
    parser.add_argument(
        "-r", "--reg", help="regex for filtering repositories to show", default=None
    )
    args = parser.parse_args()
    return os.path.normpath(args.dir), args.reg


def get_repos(fullpath_start_dir, regex):
    directories = {
        dirname: os.path.join(fullpath_start_dir, dirname)
        for dirname in os.listdir(fullpath_start_dir)
        if os.path.isdir(os.path.join(fullpath_start_dir, dirname))
    }

    if regex:
        directories = filter_directories_by_regex(directories, regex)

    return [
        GitRepo(dirname, fullpath)
        for dirname, fullpath in directories.items()
        if is_git_repo(fullpath)
    ]


def filter_directories_by_regex(directories, regex):
    try:
        pattern = re.compile(regex)
    except:
        print(f"{Style.RED}Invalid regex!{Style.RESET}")
        sys.exit(1)
    directories = {
        dirname: fullpath
        for dirname, fullpath in directories.items()
        if pattern.search(dirname)
    }
    return directories


def is_git_repo(fullpath):
    return ".git" in os.listdir(fullpath) and os.path.isdir(os.path.join(fullpath, ".git"))


class GitCommand(ABC):
    message = None

    @abstractmethod
    def setup_process(self, repo):
        pass

    @abstractmethod
    def handle_output(self, repo):
        pass

    @staticmethod
    def popen_process(args, path):
        proc = subprocess.Popen(
            args,
            cwd=path,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return proc


class GitCommandsExecutor:
    def run_processes(self, repos, git_command: GitCommand):
        elligible_repos = [
            repo for repo in repos if git_command.is_repo_relevant(repo)
        ]
        git_procs = self._setup_processes(elligible_repos, git_command)
        self._handle_processes(elligible_repos, git_procs, git_command)

    @staticmethod
    def _setup_processes(repos, git_command: GitCommand):
        git_procs = []
        for repo in repos:
            git_proc = git_command.setup_process(repo)
            git_procs.append(git_proc)
        return git_procs

    @staticmethod
    def _handle_processes(repos, processes, git_command: GitCommand):
        for repo, git_proc in zip(repos, processes):
            out, _ = git_proc.communicate()
            output = out.decode().strip()
            returncode = git_proc.returncode
            git_command.handle_output(repo, output, returncode)


class GitCurrentBranch(GitCommand):
    message = "Getting current branches..."

    def setup_process(self, repo):
        command_args = ["git", "branch", "--show-current"]
        return self.popen_process(command_args, path=repo.fullpath)

    @staticmethod
    def is_repo_relevant(repo):
        return True

    @staticmethod
    def handle_output(repo, output, returncode):
        if output and returncode == 0:
            repo.on_branch = True
            repo.current_branch = output
        else:
            repo.on_branch = False
            repo.current_branch = "-- No branch --"
            repo.commits_ahead = "N/A"
            repo.commits_behind = "N/A"


class GitFetchOrigin(GitCommand):
    message = "Fetching remote state..."

    def setup_process(self, repo):
        command_args = ["git", "fetch", "origin", repo.current_branch]
        return self.popen_process(command_args, path=repo.fullpath)

    @staticmethod
    def is_repo_relevant(repo):
        return True

    @staticmethod
    def handle_output(repo, output, returncode):
        repo.has_upstream = returncode == 0
        if not repo.has_upstream:
            repo.commits_ahead = "N/A"
            repo.commits_behind = "N/A"



class GitUpstreamBranch(GitCommand):
    message = "Getting upstream branches..."

    def setup_process(self, repo):
        command_args = ["git", "rev-parse", "--abbrev-ref", repo.current_branch + "@{upstream}"]
        return self.popen_process(command_args, path=repo.fullpath)

    @staticmethod
    def is_repo_relevant(repo):
        return repo.on_branch

    @staticmethod
    def handle_output(repo, output, returncode):
        if returncode == 0:
            repo.upstream_branch = output
        else:
            repo.commits_ahead = "N/A"
            repo.commits_behind = "N/A"


class GitCommitsState(GitCommand):
    message = "Getting commits state..."

    def setup_process(self, repo):
        command_args = [
            "git",
            "rev-list",
            "--left-right",
            "--count",
            repo.current_branch + "..." + repo.upstream_branch,
        ]
        return self.popen_process(command_args, path=repo.fullpath)

    @staticmethod
    def is_repo_relevant(repo):
        return repo.has_upstream

    @staticmethod
    def handle_output(repo, output, returncode):
        ahead, behind = output.split()
        repo.commits_ahead = int(ahead)
        repo.commits_behind = int(behind)


class GitRepo:
    def __init__(self, name, fullpath):
        self.fullpath = fullpath
        self.name = name
        self.on_branch = None
        self.has_upstream = None
        self.current_branch = "N/A"
        self.upstream_branch = "N/A"
        self.commits_ahead = "N/A"
        self.commits_behind = "N/A"

    @property
    def status(self):
        if not self.has_upstream or not self.on_branch or self.commits_ahead == "N/A":
            return Status.MODERATE
        elif self.commits_behind == 0 and self.commits_ahead == 0:
            return Status.OK
        elif self.commits_behind > 0:
            return Status.CRITICAL
        else:
            return Status.MODERATE

    def __repr__(self):
        return f"GitRepo(fullpath={self.fullpath}, name={self.name})"


class Style:
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    UNDERLINE = "\033[4m"
    RESET = "\033[0m"


class Status(Enum):
    OK = "OK"
    MODERATE = "MODERATE"
    CRITICAL = "CRITICAL"


STATUS_COLOR_MAPPING = {
    Status.OK: Style.GREEN,
    Status.MODERATE: Style.YELLOW,
    Status.CRITICAL: Style.RED,
}


if __name__ == "__main__":
    main()
