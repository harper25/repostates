# microservices-git-state

The goal of the tool is to provide short insight about the state of a **set of git repositories** with one command.

The script *fetches* origin for each repository and then displays the following info:
- current branch
- commits ahead origin
- commits behind origin

![](/screen.png)

### Background story

Basically, when I wanted to run integration tests locally for a project with microservice architecture (with Docker and docker-compose) I always had to check every repository if the branch is correct and up to date (new commits from other developers). That meant either running multiple commands from the terminal or clicking through a Git client UI.
This project was created to overcome this inconvenience by automating repetitive actions with a simple command line utility.
The tool, when run, presents a short summary in a table format which shows which repositories are up-to-date and which ones have to be updated or investigated more carefully.

## Getting Started & Installing

The script is created using only inbuild Python3 libraries, so there is no need to use a virtual environment or install anything else then what is already provided with standard Python distribution.

Then, the best option to run the tool is to clone the repository and:
- use the tool directly

    ```sh
    ~/<path-to-microservices-git-state>/repostates.py --help
    ```
- or create a suitable alias in `.zshrc` or `.bash_profile`, e.g.:

    ```sh
    alias repostates="python3 /<path-to-microservices-git-state>/repostates.py"
    ```

    It is possible to append the new alias to your shell init script by running:

    ```sh
    echo 'alias repostates="python3 /<path-to-microservices-git-state>/repostates.py"' >> ~/.zshrc
    ```

    And then run:
    ```sh
    repostates --help
    ```

## Usage

```bash
$ repostates --help

usage: repostates.py [-h] [-d [DIR]] [-r REG] [--verbose] {status,pull,checkout,gone-branches,shell} ...

positional arguments:
  {status,pull,checkout,gone-branches,shell}
                        choose a command to run
    status              run git status (default)
    pull                run git pull
    checkout            run git checkout
    gone-branches       find already gone branches, default action is list
    shell               run arbitrary shell command

options:
  -h, --help            show this help message and exit
  -d [DIR], --dir [DIR]
                        directory with your git repositories, defaults to the current directory
  -r REG, --reg REG     regex for filtering repositories to show
  --verbose, -v
```

## Alternatives

- https://github.com/tj/git-extras git-bulk
- https://github.com/nosarthur/gita
- https://github.com/gruntwork-io/git-xargs
- https://github.com/GerritCodeReview/git-repo
- https://github.com/mnagel/clustergit
- https://github.com/lukasz-lobocki/gitas

## License

MIT License

## Contributing

Please, create pull requests in order to contribute.

### Taskfile

List possible linting commands with Taskfile:

```sh
task
```

Link: https://taskfile.dev/#/

## Authors

* [harper25](https://github.com/harper25)
