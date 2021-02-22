import argparse
import os
import re
import subprocess
import sys


def main():
    fullpath_start_dir, regex = get_cli_arguments()
    repos = get_repos(fullpath_start_dir, regex)

    git_commander = GitCommander(repos)
    git_commander.get_current_branches()
    git_commander.get_upstream_branches()
    git_commander.get_commits_state()

    print(f"\n{Style.BLUE}{'REPOSITORY':<40}{'BRANCH':<50}COMMITS{Style.RESET}")
    print(f"{Style.BLUE}{Style.UNDERLINE}{'':<40}{'':<50}AHEAD/BEHIND{Style.RESET}")
    for repo in git_commander.repos:
        print(repo)


def get_cli_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--dir", help="Directory", default=os.getcwd())
    parser.add_argument("-r", "--reg", help="Regex", default=None)
    args = parser.parse_args()
    return os.path.normpath(args.dir), args.reg


def get_repos(fullpath_start_dir, regex):
    directories = {
        dirname: os.path.join(fullpath_start_dir, dirname)
        for dirname in os.listdir(fullpath_start_dir)
        if os.path.isdir(os.path.join(fullpath_start_dir, dirname))
    }

    if regex:
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

    return [
        GitRepo(dirname, fullpath)
        for dirname, fullpath in directories.items()
        if is_git_repo(fullpath)
    ]


def is_git_repo(fullpath):
    return ".git" in os.listdir(fullpath)


class GitCommander:
    def __init__(self, repos):
        self.repos = repos

    def get_current_branches(self):
        git_procs = []
        for repo in self.repos:
            git_proc = GitCommander.proc_git_branch(repo.fullpath)
            git_procs.append(git_proc)

        for repo, git_proc in zip(self.repos, git_procs):
            out, _ = git_proc.communicate()
            repo.current_branch = out.decode().strip()

    def get_upstream_branches(self):
        git_procs = []
        for repo in self.repos:
            git_proc = GitCommander.proc_git_upstream_branch(repo.fullpath, repo.current_branch)
            git_procs.append(git_proc)

        for repo, git_proc in zip(self.repos, git_procs):
            out, _ = git_proc.communicate()
            output = out.decode().strip()
            code = git_proc.returncode
            if code == 0:
                repo.upstream_branch = output
            else:
                repo.commits_ahead = "N/A"
                repo.commits_behind = "N/A"

    def get_commits_state(self):
        git_procs = []
        repos_with_upstream = [repo for repo in self.repos if repo.upstream_branch]
        for repo in repos_with_upstream:
            git_proc = GitCommander.proc_git_commits_state(
                repo.fullpath, repo.current_branch, repo.upstream_branch
            )
            git_procs.append(git_proc)

        for repo, git_proc in zip(repos_with_upstream, git_procs):
            out, _ = git_proc.communicate()
            output = out.decode().strip()
            ahead, behind = output.split()
            repo.commits_ahead = int(ahead)
            repo.commits_behind = int(behind)

    @classmethod
    def proc_git_branch(cls, repo_fullpath):
        proc = subprocess.Popen(
            ["git", "branch", "--show-current"],
            cwd=repo_fullpath,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        return proc

    @classmethod
    def proc_git_upstream_branch(cls, repo_fullpath, current_branch):
        proc = subprocess.Popen(
            ["git", "rev-parse", "--abbrev-ref", current_branch + "@{upstream}"],
            cwd=repo_fullpath,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return proc

    @classmethod
    def proc_git_commits_state(cls, repo_fullpath, current_branch, upstream_branch):
        proc = subprocess.Popen(
            [
                "git",
                "rev-list",
                "--left-right",
                "--count",
                current_branch + "..." + upstream_branch,
            ],
            cwd=repo_fullpath,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        return proc


class GitRepo:
    def __init__(self, name, fullpath):
        self.fullpath = fullpath
        self.name = name
        self.current_branch = ""
        self.upstream_branch = ""
        self.commits_ahead = ""
        self.commits_behind = ""

        # self._color = ""  # property?

    def __str__(self):
        if not self.upstream_branch:
            color = Style.YELLOW
        elif self.commits_behind == 0 and self.commits_ahead == 0:
            color = Style.GREEN
        elif self.commits_behind > 0:
            color = Style.RED
        else:
            color = Style.YELLOW
        return (
            f"{color}{self.name:<40}"
            f"{self.current_branch:<50}"
            f"{self.commits_ahead:<4}"
            f"{self.commits_behind}{Style.RESET}"
        )

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


# table formatter class with default format?


if __name__ == "__main__":
    main()
