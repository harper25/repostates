import argparse
import os
import re
import subprocess
import sys
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Tuple


def main() -> None:
    common_args, flow_args = get_cli_arguments()
    repos = get_repos(fullpath_start_dir=common_args["dir"], regex=common_args["reg"])

    if not repos:
        print(f"{Style.YELLOW}No repos found!{Style.RESET}")
        return

    git_command_executor = GitCommandsExecutor()
    # pipeline = [
    #     GitCurrentBranch(),
    #     GitFetchBranch(),
    #     GitUpstreamBranch(),
    #     GitCommitsState(),
    # ]
    pipeline = [GitFetchPrune(), GitStatusBranch()]

    if flow_args["pull"]:
        pipeline.extend([GitPull(), GitStatusBranch()])
    elif flow_args["checkout"]:
        pipeline.extend(
            [GitCheckout(target_branch=flow_args["checkout"]), GitStatusBranch()]
        )

    present_git_pipeline_flow(pipeline)

    move_coursor_up(len(pipeline))
    for git_command in pipeline:
        git_command_executor.run_processes(repos, git_command)
        print(git_command.message, "\t✓")

    present_table_summary(repos)


def move_coursor_up(count: int) -> None:
    sys.stdout.write("\u001b[" + str(count) + "A")


def present_git_pipeline_flow(pipeline: List["GitCommand"]) -> None:
    for git_command in pipeline:
        print(git_command.message)


def present_table_summary(repos: List["GitRepo"]) -> None:
    header_name = "REPOSITORY"
    header_branch = "BRANCH"

    def get_column_width(header: str, content: List[str], margin: int = 3) -> int:
        max_width_content = max(len(row) for row in content)
        column_width = max(len(header), max_width_content) + margin
        return column_width

    repo_names = [repo.name for repo in repos]
    branch_names = [repo.current_branch for repo in repos]
    col_width_name = get_column_width(header_name, repo_names)
    col_width_branch = get_column_width(header_branch, branch_names)

    print(
        f"\n{Style.BLUE}{header_name:<{col_width_name}}"
        f"{header_branch:<{col_width_branch}}COMMITS{Style.RESET}"
    )
    print(
        f"{Style.BLUE}{Style.UNDERLINE}{'':<{col_width_name}}{'':<{col_width_branch}}"
        f"AHEAD/BEHIND{Style.RESET}"
    )
    for repo in sorted(repos, key=lambda repo: repo.name):
        print(
            f"{STATUS_COLOR_MAPPING[repo.status]}{repo.name:<{col_width_name}}"
            f"{repo.current_branch:<{col_width_branch}}"
            f"{repo.commits_ahead:<4}"
            f"{repo.commits_behind}{Style.RESET}"
        )


def get_cli_arguments() -> Tuple[Dict[str, Any], Dict[str, Any]]:
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
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--pull", action="store_true", default=False)
    group.add_argument("--checkout", default=None)
    args = parser.parse_args()
    common_args = {"dir": os.path.abspath(args.dir), "reg": args.reg}
    flow_args = {k: v for k, v in vars(args).items() if k not in common_args.keys()}
    return common_args, flow_args


def get_repos(fullpath_start_dir: str, regex: str) -> List["GitRepo"]:
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


def filter_directories_by_regex(
    directories: Dict[str, str], regex: str
) -> Dict[str, str]:
    try:
        pattern = re.compile(regex)
    except re.error:
        print(f"{Style.RED}Invalid regex!{Style.RESET}")
        sys.exit(1)
    directories = {
        dirname: fullpath
        for dirname, fullpath in directories.items()
        if pattern.search(dirname)
    }
    return directories


def is_git_repo(fullpath: str) -> bool:
    return os.path.isdir(os.path.join(fullpath, ".git"))


class GitCommand(ABC):
    message: str

    @abstractmethod
    def setup_process(self, repo: "GitRepo") -> subprocess.Popen:
        pass

    @abstractmethod
    def handle_output(self, repo: "GitRepo", output: str, returncode: int) -> None:
        pass

    @abstractmethod
    def is_relevant(self, repo: "GitRepo") -> bool:
        pass

    @staticmethod
    def popen_process(args: List[str], path: str) -> subprocess.Popen:
        proc = subprocess.Popen(
            args,
            cwd=path,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return proc


class GitCommandsExecutor:
    def run_processes(self, repos: List["GitRepo"], git_command: GitCommand) -> None:
        elligible_repos = [repo for repo in repos if git_command.is_relevant(repo)]
        git_procs = self._setup_processes(elligible_repos, git_command)
        self._handle_processes(elligible_repos, git_procs, git_command)

    @staticmethod
    def _setup_processes(
        repos: List["GitRepo"], git_command: GitCommand
    ) -> List[subprocess.Popen]:
        git_procs: List[subprocess.Popen] = []
        for repo in repos:
            git_proc = git_command.setup_process(repo)
            git_procs.append(git_proc)
        return git_procs

    @staticmethod
    def _handle_processes(
        repos: List["GitRepo"],
        processes: List[subprocess.Popen],
        git_command: GitCommand,
    ) -> None:
        for repo, git_proc in zip(repos, processes):
            out, _ = git_proc.communicate()
            output = out.decode().strip()
            returncode = git_proc.returncode
            git_command.handle_output(repo, output, returncode)


class GitCurrentBranch(GitCommand):
    message = "Getting current branches..."

    def setup_process(self, repo: "GitRepo") -> subprocess.Popen:
        command_args = ["git", "branch", "--show-current"]
        return self.popen_process(command_args, path=repo.fullpath)

    @staticmethod
    def is_relevant(repo: "GitRepo") -> bool:
        return True

    @staticmethod
    def handle_output(repo: "GitRepo", output: str, returncode: int) -> None:
        if output and returncode == 0:
            repo.on_branch = True
            repo.current_branch = output
        else:
            repo.on_branch = False
            repo.current_branch = "-- No branch --"
            repo.commits_ahead = "N/A"
            repo.commits_behind = "N/A"


class GitFetchBranch(GitCommand):
    message = "Fetching current branches..."

    def setup_process(self, repo: "GitRepo") -> subprocess.Popen:
        command_args = ["git", "fetch", "origin", repo.current_branch]
        return self.popen_process(command_args, path=repo.fullpath)

    @staticmethod
    def is_relevant(repo: "GitRepo") -> bool:
        return True

    @staticmethod
    def handle_output(repo: "GitRepo", output: str, returncode: int) -> None:
        repo.has_upstream = returncode == 0
        if not repo.has_upstream:
            repo.commits_ahead = "N/A"
            repo.commits_behind = "N/A"


class GitFetchPrune(GitCommand):
    message = "Fetching origin with prune..."

    def setup_process(self, repo: "GitRepo") -> subprocess.Popen:
        command_args = ["git", "fetch", "origin", "--prune"]
        return self.popen_process(command_args, path=repo.fullpath)

    @staticmethod
    def is_relevant(repo: "GitRepo") -> bool:
        return True

    @staticmethod
    def handle_output(repo: "GitRepo", output: str, returncode: int) -> None:
        repo.has_upstream = returncode == 0
        if not repo.has_upstream:
            repo.current_branch = "-- No upstream --"
            repo.commits_ahead = "N/A"
            repo.commits_behind = "N/A"


class GitUpstreamBranch(GitCommand):
    message = "Getting upstream branches..."

    def setup_process(self, repo: "GitRepo") -> subprocess.Popen:
        command_args = [
            "git",
            "rev-parse",
            "--abbrev-ref",
            repo.current_branch + "@{upstream}",  # noqa: FS003 f-string missing prefix
        ]
        return self.popen_process(command_args, path=repo.fullpath)

    @staticmethod
    def is_relevant(repo: "GitRepo") -> bool:
        return repo.on_branch

    @staticmethod
    def handle_output(repo: "GitRepo", output: str, returncode: int) -> None:
        if returncode == 0:
            repo.upstream_branch = output
        else:
            repo.commits_ahead = "N/A"
            repo.commits_behind = "N/A"


class GitCommitsState(GitCommand):
    message = "Getting commits state..."

    def setup_process(self, repo: "GitRepo") -> subprocess.Popen:
        command_args = [
            "git",
            "rev-list",
            "--left-right",
            "--count",
            repo.current_branch + "..." + repo.upstream_branch,
        ]
        return self.popen_process(command_args, path=repo.fullpath)

    @staticmethod
    def is_relevant(repo: "GitRepo") -> bool:
        return repo.has_upstream

    @staticmethod
    def handle_output(repo: "GitRepo", output: str, returncode: int) -> None:
        ahead, behind = output.split()
        repo.commits_ahead = ahead
        repo.commits_behind = behind


class GitStatus(GitCommand):
    message = "Getting git status..."

    def setup_process(self, repo: "GitRepo") -> subprocess.Popen:
        command_args = ["git", "status", "--porcelain=v2"]
        return self.popen_process(command_args, path=repo.fullpath)

    @staticmethod
    def is_relevant(repo: "GitRepo") -> bool:
        return True

    @staticmethod
    def handle_output(repo: "GitRepo", output: str, returncode: int) -> None:
        result = re.findall("^(?!# branch).+", output, re.MULTILINE)
        repo.is_clean = len(result) == 0
        if not repo.is_clean:
            repo.current_branch = "*" + repo.current_branch


class GitStatusBranch(GitCommand):
    "GitFetchPrune required first to detect the case with missing remote branch."

    message = "Detailed git status..."

    def setup_process(self, repo: "GitRepo") -> subprocess.Popen:
        command_args = ["git", "status", "--porcelain=v2", "--branch"]
        return self.popen_process(command_args, path=repo.fullpath)

    @staticmethod
    def is_relevant(repo: "GitRepo") -> bool:
        return repo.has_upstream

    @staticmethod
    def handle_output(repo: "GitRepo", output: str, returncode: int) -> None:
        result = re.findall(r"# branch.head\s(.*)", output, re.MULTILINE)
        repo.on_branch = result[0] != "(detached)"
        repo.current_branch = result[0] if repo.on_branch else "-- No branch --"

        result = re.findall(r"# branch.upstream\s(.*)", output, re.MULTILINE)
        repo.has_upstream = len(result) > 0
        repo.upstream_branch = result[0] if repo.has_upstream else None

        result = re.findall(r"# branch.ab\s[+-](\d*)\s[+-](\d*)", output, re.MULTILINE)
        if result:
            repo.commits_ahead = result[0][0]
            repo.commits_behind = result[0][1]

        result = re.findall(r"^(?!# branch).+", output, re.MULTILINE)
        repo.is_clean = len(result) == 0
        if not repo.is_clean:
            repo.current_branch = "*" + repo.current_branch


class GitCheckout(GitCommand):
    message = "Running git checkout..."

    def __init__(self, target_branch: str) -> None:
        self.target_branch = target_branch

    def setup_process(self, repo: "GitRepo") -> subprocess.Popen:
        command_args = ["git", "checkout", self.target_branch]
        return self.popen_process(command_args, path=repo.fullpath)

    @staticmethod
    def is_relevant(repo: "GitRepo") -> bool:
        return repo.is_clean

    @staticmethod
    def handle_output(repo: "GitRepo", output: str, returncode: int) -> None:
        pass


class GitPull(GitCommand):
    message = "Running git pull..."

    def setup_process(self, repo: "GitRepo") -> subprocess.Popen:
        command_args = ["git", "pull"]
        return self.popen_process(command_args, path=repo.fullpath)

    @staticmethod
    def is_relevant(repo: "GitRepo") -> bool:
        return repo.is_clean

    @staticmethod
    def handle_output(repo: "GitRepo", output: str, returncode: int) -> None:
        pass


class GitRepo:
    def __init__(self, name: str, fullpath: str) -> None:
        self.fullpath = fullpath
        self.name = name
        self.on_branch: bool = False
        self.has_upstream: bool = False
        self.is_clean: bool = False
        self.current_branch: str = "N/A"
        self.upstream_branch: str = "N/A"
        self.commits_ahead: str = "N/A"
        self.commits_behind: str = "N/A"

    @property
    def status(self) -> "Status":
        if not self.has_upstream or not self.on_branch or self.commits_ahead == "N/A":
            return Status.MODERATE
        elif int(self.commits_behind) == 0 and int(self.commits_ahead) == 0:
            return Status.OK
        elif int(self.commits_behind) > 0:
            return Status.CRITICAL
        else:
            return Status.MODERATE

    def __repr__(self) -> str:
        return f"GitRepo(fullpath={self.fullpath}, name={self.name})"

    def __eq__(self, other: object) -> bool:
        return self.__dict__ == other.__dict__


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
