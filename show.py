import argparse
import os
import re
import sys


def main():
    fullpath_start_dir, regex = get_cli_arguments()
    dir_names = get_directories(fullpath_start_dir, regex)
    print(dir_names)


def get_cli_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--dir", help="Directory", default=os.getcwd())
    parser.add_argument("-r", "--reg", help="Regex", default=None)
    args = parser.parse_args()
    return os.path.normpath(args.dir), args.reg


def get_directories(start_directory, regex):
    # names - filtering
    # fullpaths - necessary for git operations
    directories = [
        file_or_dir for file_or_dir in os.listdir(start_directory)
        if os.path.isdir(os.path.join(start_directory, file_or_dir))
    ]
    if regex:
        try:
            pattern = re.compile(regex)
        except:
            print("Invalid regex!")
            sys.exit(1)
        directories = [dir for dir in directories if pattern.search(dir)]

    return directories


def is_git_repo(fullpath):
    # ".git" in
    return True


class Style:
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    UNDERLINE = '\033[4m'
    RESET = '\033[0m'


class GitRepo:
    def __init__(self, fullpath):
        self.fullpath = fullpath
        self.name = os.path.dirname(fullpath)
        self.current_branch = ""
        self.upstream_branch = ""
        self.commits_behind = ""

    def __str__(self):
        if not self.commits_behind:
            color = Style.YELLOW
        elif int(self.commits_behind) == 0:
            color = Style.GREEN
        elif int(self.commits_behind) > 0:
            color = Style.RED
        else:
            color = Style.YELLOW
        return (
            f"{color}{self.name:<40} "
            f"{self.current_branch:<50} "
            f"{self.commits_behind}{Style.RESET}"
        )


if __name__ == "__main__":
    main()
