import argparse
import os
import re
import subprocess
import sys
from enum import Enum


def main():
    fullpath_start_dir, regex = get_cli_arguments()
    repos = get_repos(fullpath_start_dir, regex)

    if not repos:
        print(f"{Style.YELLOW}No repos found!{Style.RESET}")
        return

    git_commander = GitCommander(repos)
    print("Preparation...")
    git_commander.get_current_branches()
    print("Fetching...")
    git_commander.get_fetched_branches()
    git_commander.get_upstream_branches()
    print("Gathering state...")
    git_commander.get_commits_state()
    present_table_summary(repos)


def present_table_summary(repos):
    header_name = "REPOSITORY"
    header_branch = "BRANCH"
    margin = 3
    col_width_name = max(max(len(repo.name) for repo in repos), len(header_name)) + margin
    col_width_branch = (
        max(max(len(repo.current_branch) for repo in repos), len(header_branch)) + margin
    )

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


class GitCommander:
    def __init__(self, repos):
        self.repos = repos

    @property
    def repos_with_upstream(self):
        return [repo for repo in self.repos if repo.has_upstream is not False]

    @staticmethod
    def setup_processes(repos, process_fcn):
        git_procs = []
        for repo in repos:
            git_proc = process_fcn(repo)
            git_procs.append(git_proc)
        return git_procs

    @staticmethod
    def handle_processes(repos, processes, output_handler_fcn):
        for repo, git_proc in zip(repos, processes):
            out, _ = git_proc.communicate()
            output = out.decode().strip()
            returncode = git_proc.returncode
            output_handler_fcn(repo, output, returncode)  # return repo? state mutation

    def run_processes(self, repos, process_fcn, handle_fcn):
        git_procs = self.setup_processes(repos, process_fcn)
        self.handle_processes(repos, git_procs, handle_fcn)

    def get_current_branches(self):
        self.run_processes(
            self.repos,
            self.proc_git_branch,
            self.handle_git_branch_process
        )

    def get_fetched_branches(self):
        self.run_processes(
            self.repos_with_upstream,
            self.proc_git_fetch_branch,
            self.handle_git_fetch_process
        )

    def get_upstream_branches(self):
        self.run_processes(
            self.repos_with_upstream,
            self.proc_git_upstream_branch,
            self.handle_get_upstream_branches
        )

    def get_commits_state(self):
        self.run_processes(
            self.repos_with_upstream,
            self.proc_git_commits_state,
            self.handle_get_commits_state
        )

    def proc_git_branch(self, repo):
        command_args = ["git", "branch", "--show-current"]
        return self.popen_process(command_args, path=repo.fullpath)

    def proc_git_upstream_branch(self, repo):
        command_args = ["git", "rev-parse", "--abbrev-ref", repo.current_branch + "@{upstream}"]
        return self.popen_process(command_args, path=repo.fullpath)

    def proc_git_fetch_branch(self, repo):
        command_args = ["git", "fetch", "origin", repo.current_branch]
        return self.popen_process(command_args, path=repo.fullpath)

    def proc_git_commits_state(self, repo):
        command_args = [
            "git",
            "rev-list",
            "--left-right",
            "--count",
            repo.current_branch + "..." + repo.upstream_branch,
        ]
        return self.popen_process(command_args, path=repo.fullpath)

    @staticmethod
    def handle_git_branch_process(repo, output, returncode):
        if output and returncode == 0:
            repo.current_branch = output
        else:
            repo.has_upstream = False  # fix, two usages
            repo.current_branch = "-- No branch --"
            repo.commits_ahead = "N/A"
            repo.commits_behind = "N/A"

    @staticmethod
    def handle_get_upstream_branches(repo, output, returncode):
        if returncode == 0:
            repo.upstream_branch = output
        else:
            repo.commits_ahead = "N/A"
            repo.commits_behind = "N/A"

    @staticmethod
    def handle_git_fetch_process(repo, output, returncode):
        repo.has_upstream = returncode == 0
        if not repo.has_upstream:
            repo.commits_ahead = "N/A"
            repo.commits_behind = "N/A"

    @staticmethod
    def handle_get_commits_state(repo, output, returncode):
        ahead, behind = output.split()
        repo.commits_ahead = int(ahead)
        repo.commits_behind = int(behind)

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


class GitRepo:
    def __init__(self, name, fullpath):
        self.fullpath = fullpath
        self.name = name
        self.has_upstream = None
        self.current_branch = ""
        self.upstream_branch = ""
        self.commits_ahead = ""
        self.commits_behind = ""

    @property
    def status(self):
        if not self.has_upstream:
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
