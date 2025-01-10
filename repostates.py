import argparse
import logging
import os
import re
import shlex
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
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
        "-r", "--reg", help="regex for filtering repositories to show", default=None
    )
    parser.add_argument("--verbose", "-v", action="count", default=0)
    subparsers = parser.add_subparsers(dest="command", help="choose a command to run")
    parser_status = subparsers.add_parser(  # noqa: F841
        "status", help="run git status (default)"
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
    parser_shell = subparsers.add_parser("shell", help="run arbitrary shell command")
    parser_shell.add_argument("custom_command", help="custom shell command to run")
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
    pipeline = [GitFetchPrune(), GitStatusBranch()]
    if flow_args["command"] == "pull":
        pipeline.extend([GitPull(), GitStatusBranch()])
    elif flow_args["command"] == "checkout":
        pipeline.extend(
            [GitCheckout(target_branch=flow_args["target_branch"]), GitStatusBranch()]
        )
    elif flow_args["command"] == "gone-branches":
        pipeline.append(GitGoneBranches())
    elif flow_args["command"] == "shell":
        pipeline.extend(
            [
                CustomCommand(custom_command=flow_args["custom_command"]),
                GitStatusBranch(),
            ]
        )
    return pipeline


def move_coursor_up(count: int) -> None:
    sys.stdout.write("\u001b[" + str(count) + "A")


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
                LOGGER.debug(
                    f"Skipping {git_command.__class__.__name__} for {repo.name}"
                )
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
            if error:
                LOGGER.warning(
                    f"{Style.GREEN}{git_command.__class__.__name__}{Style.RESET} for {Style.GREEN}{repo.name}{Style.RESET}:\n\terror code: "
                    f"{returncode}\n\t{indent_multiline_log(error)}"
                )
            if output:
                LOGGER.debug(
                    f"{Style.GREEN}{git_command.__class__.__name__}{Style.RESET} output for {Style.GREEN}{repo.name}{Style.RESET}:"
                    f"\n\t{indent_multiline_log(output)}"
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


class GitStatus(GitCommand):
    message = "Getting git status..."

    def setup_process(self, repo: "GitRepo") -> subprocess.Popen:
        command_args = ["git", "status", "--porcelain=v2"]
        return self.popen_process(command_args, path=repo.fullpath)

    @staticmethod
    def is_relevant(repo: "GitRepo") -> bool:
        return True

    @staticmethod
    def handle_output(repo: "GitRepo", returncode: int, output: str, error: str) -> None:
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
        return True

    @staticmethod
    def handle_output(repo: "GitRepo", returncode: int, output: str, error: str) -> None:
        if returncode != 0:
            repo.current_branch = "-- No branch --"
            repo.commits_ahead = "N/A"
            repo.commits_behind = "N/A"
            return

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
        else:
            repo.commits_ahead = "N/A"
            repo.commits_behind = "N/A"

        result = re.findall(r"^(?!# branch).+", output, re.MULTILINE)
        repo.is_clean = len(result) == 0
        if not repo.is_clean:
            repo.current_branch = "*" + repo.current_branch


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
        return repo.is_clean

    @staticmethod
    def handle_output(repo: "GitRepo", returncode: int, output: str, error: str) -> None:
        # maybe set some flag?
        pass


class CustomCommand(GitCommand):  # fix inheritance
    # save output and error and error code? per repo per command?...
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
        # maybe set some flag?
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
    def handle_output(repo: "GitRepo", returncode: int, output: str, error: str) -> None:
        if returncode:
            LOGGER.warning(f"GitCheckout for repo '{repo.name}' returned nonzero code")
        pass


class GitGoneBranches(GitCommand):
    message = "Running git branch -vv..."

    def setup_process(self, repo: "GitRepo") -> subprocess.Popen:
        command_args = ["git", "branch", "-vv"]
        return self.popen_process(command_args, path=repo.fullpath)

    @staticmethod
    def is_relevant(repo: "GitRepo") -> bool:
        return True

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


# currently unused GitCommands, kept for reference
class GitCurrentBranch(GitCommand):
    message = "Getting current branches..."

    def setup_process(self, repo: "GitRepo") -> subprocess.Popen:
        command_args = ["git", "branch", "--show-current"]
        return self.popen_process(command_args, path=repo.fullpath)

    @staticmethod
    def is_relevant(repo: "GitRepo") -> bool:
        return True

    @staticmethod
    def handle_output(repo: "GitRepo", returncode: int, output: str, error: str) -> None:
        repo.on_branch = len(output) > 0 and returncode == 0
        repo.current_branch = output if repo.on_branch else "-- No branch --"


class GitFetchBranch(GitCommand):
    message = "Fetching current branches..."

    def setup_process(self, repo: "GitRepo") -> subprocess.Popen:
        command_args = ["git", "fetch", "origin", repo.current_branch]
        return self.popen_process(command_args, path=repo.fullpath)

    @staticmethod
    def is_relevant(repo: "GitRepo") -> bool:
        return True

    @staticmethod
    def handle_output(repo: "GitRepo", returncode: int, output: str, error: str) -> None:
        repo.has_upstream = returncode == 0


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
    def handle_output(repo: "GitRepo", returncode: int, output: str, error: str) -> None:
        if returncode == 0:
            repo.upstream_branch = output


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
    def handle_output(repo: "GitRepo", returncode: int, output: str, error: str) -> None:
        ahead, behind = output.split()
        repo.commits_ahead = ahead
        repo.commits_behind = behind


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
        self.gone_branches: Optional[List[str]] = None

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
