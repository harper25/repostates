import argparse
import logging
import os
import re
import shlex
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple

LOGGER = logging.getLogger(os.path.basename(__file__))


@dataclass
class CommonArgs:
    working_dir: str
    regex: str
    logger_verbosity: int


def main() -> None:
    parser = create_arg_parser()
    common_args, flow_args = get_cli_arguments(parser)
    configure_logger(common_args.logger_verbosity)
    repos = get_repos(
        fullpath_start_dir=common_args.working_dir, regex=common_args.regex
    )

    if not repos:
        print(f"{Style.YELLOW}No repos found!{Style.RESET}")
        return

    # pipeline generator
    pipeline = generate_git_pipeline(flow_args)
    git_command_executor = GitCommandsExecutor()

    # pipeline execution
    for git_command in pipeline:
        print(f"{Style.MAGENTA}{git_command.message}{Style.RESET}")
        git_command_executor.run_processes(repos, git_command)
        print(f"{Style.MAGENTA}{Style.BRIGHT}{git_command.message}\t✓{Style.RESET}")

    # presentation layer - results, summary
    if flow_args["command"] == "gone-branches":
        present_gone_branches(repos)
    elif flow_args["command"] == "shell":
        print(f"\n{Style.CYAN}CUSTOM SHELL COMMAND OUTPUT:{Style.RESET}\n")
        for repo in repos:
            print(f"{Style.GREEN}{repo.name}{Style.RESET}")
            print(f"{repo.custom_cmd_output}")
            print(f"{Style.RED}{repo.custom_cmd_error}{Style.RESET}")
    else:
        present_table_summary(repos)


def create_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d",
        "--dir",
        nargs="?",
        help="directory with your git repositories, defaults to the current directory",
        default=os.getcwd(),
    )
    parser.add_argument(
        "-r",
        "--reg",
        help="regex for filtering repositories to show",
        default=None,
    )
    parser.add_argument(
        "--verbose", "-v", action="count", default=0, help="increase verbosity"
    )
    parser.add_argument(
        "--no-fetch",
        "-n",
        default=False,
        action="store_true",
        help="do not fetch before status",
    )
    subparsers = parser.add_subparsers(dest="command", help="choose a command to run")
    parser_status = subparsers.add_parser(  # noqa: F841
        "status", help="run git status (default)"
    )
    parser_status.add_argument(
        "--no-fetch",
        "-n",
        default=False,
        action="store_true",
        help="do not fetch before status",
    )
    parser_pull = subparsers.add_parser("pull", help="run git pull")  # noqa: F841
    parser_checkout = subparsers.add_parser("checkout", help="run git checkout")
    parser_checkout.add_argument("target_branch", help="branch to checkout to")
    parser_branch = subparsers.add_parser(
        "gone-branches", help="find already gone branches, default action is list"
    )
    parser_branch.add_argument(
        "subcommand",
        nargs="?",
        choices=["list"],
        default="list",
        help="choose action to perform on gone branches",
    )
    parser_shell = subparsers.add_parser(
        "shell", help="run arbitrary shell command - enclose in quotes"
    )
    parser_shell.add_argument(
        "custom_command", help="custom shell command to run - remember about quotes"
    )
    parser.set_defaults(command="status")

    return parser


def get_cli_arguments(
    parser: argparse.ArgumentParser, input_args: Optional[List[str]] = None
) -> Tuple[CommonArgs, Dict[str, Any]]:
    args = parser.parse_args(input_args)

    common_args = CommonArgs(
        working_dir=os.path.abspath(args.dir),
        regex=args.reg,
        logger_verbosity=args.verbose,
    )
    return common_args, vars(args)


def generate_git_pipeline(flow_args: Dict[str, str]) -> List["GitCommand"]:
    pipeline = [GitFetchPrune(), GitStatusBranch(), GitDescribe()]
    if flow_args["command"] == "status" and flow_args["no_fetch"]:
        return [GitStatusBranch(), GitDescribe()]
    elif flow_args["command"] == "pull":
        pipeline.extend([GitPull(), GitStatusBranch(), GitDescribe()])
    elif flow_args["command"] == "checkout":
        pipeline.extend(
            [
                GitCheckout(target_branch=flow_args["target_branch"]),
                GitStatusBranch(),
                GitDescribe(),
            ]
        )
    elif flow_args["command"] == "gone-branches":
        pipeline.append(GitGoneBranches())
    elif flow_args["command"] == "shell":
        return [CustomCommand(custom_command=flow_args["custom_command"])]
    return pipeline


def move_coursor_up(count: int) -> None:
    sys.stdout.write("\u001b[" + str(count) + "A")


def present_table_summary(repos: List["GitRepo"]) -> None:
    headers_1 = ["REPOSITORY", "BRANCH", "COMMITS"]
    headers_2 = ["", "", "AHEAD/BEHIND"]

    rows = [headers_1, headers_2]
    repo_statuses = []
    column_widths = [max(len(i1), len(i2)) for i1, i2 in zip(headers_1, headers_2)]
    for repo in sorted(repos, key=lambda repo: repo.name):
        repo_statuses.append(repo.status)
        if repo.ref:
            ref = "*" + repo.ref if repo.is_clean is False else repo.ref
        else:
            ref = "-- Not a git repo! --"
        if repo.commits_ahead is None or repo.commits_behind is None:
            commits_ahead_behind = "N/A" + " " * (4 - len("N/A")) + "N/A"
        else:
            commits_ahead_behind = (
                str(repo.commits_ahead)
                + " " * (4 - len(str(repo.commits_ahead)))  # noqa: W503
                + str(repo.commits_behind)  # noqa: W503
            )
        row = [repo.name, ref, commits_ahead_behind]
        column_widths = [
            max(len(msg), current_max_len)
            for msg, current_max_len in zip(row, column_widths)
        ]
        rows.append([repo.name, ref, commits_ahead_behind])

    margin = 3
    column_widths = [width + margin for width in column_widths]

    print(
        f"\n{Style.BLUE}{headers_1[0]:<{column_widths[0]}}"
        f"{headers_1[1]:<{column_widths[1]}}{headers_1[2]}{Style.RESET}"
    )
    print(
        f"{Style.BLUE}{Style.UNDERLINE}{headers_2[0]:<{column_widths[0]}}"
        f"{headers_2[1]:<{column_widths[1]}}{headers_2[2]}{Style.RESET}"
    )
    for row, repo_status in zip(rows[2:], repo_statuses):
        print(
            f"{STATUS_COLOR_MAPPING[repo_status]}{row[0]:<{column_widths[0]}}"
            f"{row[1]:<{column_widths[1]}}"
            f"{row[2]}{Style.RESET}"
        )


def present_gone_branches(repos: List["GitRepo"]) -> None:
    print(f"\n{Style.BLUE}ALREADY GONE BRANCHES:{Style.RESET}\n")
    for repo in repos:
        print(f"{Style.GREEN}{repo.name}{Style.RESET}")
        if repo.gone_branches:
            for branch_candidate_to_delete in repo.gone_branches:
                print(f"  {Style.RED}↳ {branch_candidate_to_delete}{Style.RESET}")


def indent_multiline_log(message: str) -> str:
    return message.replace("\n", "\n\t")


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


# https://docs.python.org/3/howto/logging.html#when-to-use-logging
def configure_logger(verbosity: int) -> None:
    loglevels = ["ERROR", "WARNING", "INFO", "DEBUG"]
    verified_verbosity = min(verbosity, 3)
    loglevel = loglevels[verified_verbosity]
    stream_formatter = logging.Formatter(
        "{levelname:<8s} {message}", style="{"  # noqa: FS003
    )
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(stream_formatter)
    LOGGER.setLevel(loglevel)
    LOGGER.addHandler(stream_handler)


class GitCommand(ABC):
    message: str

    @abstractmethod
    def setup_process(self, repo: "GitRepo") -> subprocess.Popen:
        pass

    @abstractmethod
    def handle_output(
        self, repo: "GitRepo", returncode: int, output: str, error: str
    ) -> None:
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
        elligible_repos = []
        for repo in repos:
            if not git_command.is_relevant(repo):
                LOGGER.info(f"Skipping {git_command.__class__.__name__} for {repo.name}")
                continue
            elligible_repos.append(repo)
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
            out, err = git_proc.communicate()
            returncode = git_proc.returncode
            output = out.decode().strip()
            error = err.decode().strip()
            msg = output or error
            if returncode == 0 and msg:
                LOGGER.debug(
                    f"{Style.GREEN}{git_command.__class__.__name__}{Style.RESET} "
                    f"for {Style.GREEN}{repo.name}{Style.RESET}:"
                    f"\n\t{indent_multiline_log(msg)}"
                )
            elif msg:
                LOGGER.warning(
                    f"{Style.GREEN}{git_command.__class__.__name__}{Style.RESET}"
                    f" for {Style.GREEN}{repo.name}{Style.RESET}:\n\terror code: "
                    f"{returncode}\n\t{indent_multiline_log(msg)}"
                )
            git_command.handle_output(repo, returncode, output, error)


class GitFetchPrune(GitCommand):
    message = "Fetching origin with prune..."

    def setup_process(self, repo: "GitRepo") -> subprocess.Popen:
        command_args = ["git", "fetch", "origin", "--prune"]
        return self.popen_process(command_args, path=repo.fullpath)

    @staticmethod
    def is_relevant(repo: "GitRepo") -> bool:
        return True

    @staticmethod
    def handle_output(repo: "GitRepo", returncode: int, output: str, error: str) -> None:
        repo.has_upstream = returncode == 0


class GitDescribe(GitCommand):
    message = "Checking tags..."

    def setup_process(self, repo: "GitRepo") -> subprocess.Popen:
        command_args = shlex.split("git describe --tags --exact-match")
        return self.popen_process(command_args, path=repo.fullpath)

    @staticmethod
    def is_relevant(repo: "GitRepo") -> bool:
        return repo.ref_type == GitRefType.DETACHED

    @staticmethod
    def handle_output(repo: "GitRepo", returncode: int, output: str, error: str) -> None:
        if returncode == 0:
            repo.ref_type = GitRefType.TAG
            repo.ref = f"tags/{output}"


class GitStatusBranch(GitCommand):
    message = "Detailed git status..."

    def setup_process(self, repo: "GitRepo") -> subprocess.Popen:
        command_args = ["git", "status", "--porcelain=v2", "--branch"]
        return self.popen_process(command_args, path=repo.fullpath)

    @staticmethod
    def is_relevant(repo: "GitRepo") -> bool:
        return True  # can be only local repo

    @staticmethod
    def handle_output(repo: "GitRepo", returncode: int, output: str, error: str) -> None:
        if returncode != 0:
            repo.commits_ahead = None
            repo.commits_behind = None
            return

        oid = re.findall(r"# branch.oid\s(.*)", output, re.MULTILINE)
        repo.oid = oid[0]

        head = re.findall(r"# branch.head\s(.*)", output, re.MULTILINE)
        repo.ref_type = (
            GitRefType.BRANCH if head[0] != "(detached)" else GitRefType.DETACHED
        )
        repo.ref = head[0] if repo.ref_type == GitRefType.BRANCH else repo.oid

        changes_present = re.findall(r"^(?!# branch).+", output, re.MULTILINE)
        repo.is_clean = len(changes_present) == 0

        if repo.has_upstream is False:
            return

        upstream = re.findall(r"# branch.upstream\s(.*)", output, re.MULTILINE)
        repo.has_upstream = len(upstream) > 0

        commits_ahead_behind = re.findall(
            r"# branch.ab\s[+-](\d*)\s[+-](\d*)", output, re.MULTILINE
        )
        if commits_ahead_behind:
            repo.commits_ahead = int(commits_ahead_behind[0][0])
            repo.commits_behind = int(commits_ahead_behind[0][1])
        else:
            repo.commits_ahead = None
            repo.commits_behind = None


class GitCheckout(GitCommand):
    message = "Running git checkout..."

    def __init__(self, target_branch: str) -> None:
        parsed_target_branch = target_branch.split()[0].split(";")[0]
        if parsed_target_branch != target_branch:
            LOGGER.warning(f"Incorrect target branch was given: '{target_branch}'")
            print(f"Target branch was set to: '{parsed_target_branch}'")
        self.target_branch = parsed_target_branch

    def setup_process(self, repo: "GitRepo") -> subprocess.Popen:
        command_args = ["git", "checkout", self.target_branch]
        return self.popen_process(command_args, path=repo.fullpath)

    @staticmethod
    def is_relevant(repo: "GitRepo") -> bool:
        return repo.is_clean and repo.has_upstream is True

    @staticmethod
    def handle_output(repo: "GitRepo", returncode: int, output: str, error: str) -> None:
        # maybe set some flag?
        pass


class GitPull(GitCommand):
    message = "Running git pull..."

    def setup_process(self, repo: "GitRepo") -> subprocess.Popen:
        command_args = ["git", "pull"]
        return self.popen_process(command_args, path=repo.fullpath)

    @staticmethod
    def is_relevant(repo: "GitRepo") -> bool:
        return (
            repo.is_clean
            and repo.ref_type == GitRefType.BRANCH  # noqa: W503
            and repo.has_upstream is True  # noqa: W503
        )

    @staticmethod
    def handle_output(repo: "GitRepo", returncode: int, output: str, error: str) -> None:
        # maybe set some flag?
        pass


class GitGoneBranches(GitCommand):
    message = "Running git branch -vv..."

    def setup_process(self, repo: "GitRepo") -> subprocess.Popen:
        command_args = ["git", "branch", "-vv"]
        return self.popen_process(command_args, path=repo.fullpath)

    @staticmethod
    def is_relevant(repo: "GitRepo") -> bool:
        return True  # ?

    @staticmethod
    def handle_output(repo: "GitRepo", returncode: int, output: str, error: str) -> None:
        if returncode != 0:
            repo.gone_branches = []
            return

        repo.gone_branches = [
            branch.split()[0]
            for branch in output.split("\n")
            if "gone]" in branch and not branch.startswith("*")
        ]


class CustomCommand(GitCommand):  # fix inheritance
    def __init__(self, custom_command: str) -> None:
        self.custom_command = custom_command
        self.message = f"Running custom command: {custom_command}"
        LOGGER.info(f"Custom command: {custom_command}")

    def setup_process(self, repo: "GitRepo") -> subprocess.Popen:
        command_args = shlex.split(self.custom_command)
        return self.popen_process(command_args, path=repo.fullpath)

    @staticmethod
    def is_relevant(repo: "GitRepo") -> bool:
        return True

    @staticmethod
    def handle_output(repo: "GitRepo", returncode: int, output: str, error: str) -> None:
        repo.custom_cmd_return_code = returncode
        repo.custom_cmd_output = output
        repo.custom_cmd_error = error


class GitRefType(Enum):
    UNKNOWN = auto()
    DETACHED = auto()
    BRANCH = auto()
    TAG = auto()
    COMMIT = auto()


class GitRepo:
    def __init__(self, name: str, fullpath: str) -> None:
        self.fullpath = fullpath
        self.name = name
        self.oid: Optional[str] = None
        self.ref: Optional[str] = None
        self.ref_type: GitRefType = GitRefType.UNKNOWN
        self.has_upstream: Optional[bool] = None
        self.is_clean: bool = False
        self.commits_ahead: Optional[int] = None
        self.commits_behind: Optional[int] = None
        self.gone_branches: Optional[List[str]] = None
        self.custom_cmd_return_code: Optional[int] = None
        self.custom_cmd_output: Optional[str] = None
        self.custom_cmd_error: Optional[str] = None

    @property
    def status(self) -> "Status":
        if self.ref_type == GitRefType.UNKNOWN:
            return Status.CRITICAL
        elif (
            not self.has_upstream
            or self.ref_type != GitRefType.BRANCH  # noqa: W503
            or self.commits_ahead is None  # noqa: W503
            or self.commits_behind is None  # noqa: W503
        ):
            return Status.MODERATE
        elif self.commits_behind == 0 and self.commits_ahead == 0:
            return Status.OK
        elif self.commits_behind > 0:
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

    BRIGHT = "\033[1m"
    DIM = "\033[2m"
    ITALICS = "\033[3m"
    UNDERLINE = "\033[4m"
    NORMAL = "\033[22m"

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
