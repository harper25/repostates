# ARCHIVE

## Deprecated GitCommands

GitCommands kept for reference - in case needed in the future

```py
# DEPRECATED GitCommands - kept for reference
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
```
