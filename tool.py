import argparse
import os

parser = argparse.ArgumentParser()
parser.add_argument(
    "-d",  # change shortcut? how is it used in different libs to indicate path?
    "--dir",
    nargs="?",
    help="directory with your git repositories, defaults to the current directory",
    default=os.getcwd(),
)
parser.add_argument(
    "-r", "--reg", help="regex for filtering repositories to show", default=None
)
subparsers = parser.add_subparsers(dest="command", help="sub-command help")

parser_status = subparsers.add_parser("status", help="status")

parser_pull = subparsers.add_parser("pull", help="a help")

parser_checkout = subparsers.add_parser("checkout", help="b help")
parser_checkout.add_argument("branch", help="baz help")

parser_branch = subparsers.add_parser("branch", help="a help")

input_args = []
args0 = parser.parse_args(input_args)  # should be status
print(input_args)
print(args0)

input_args = ["--dir", "/root"]
args1 = parser.parse_args(input_args)  # should be status
print(input_args)
print(args1)

input_args = ["checkout", "dev"]
args2 = parser.parse_args(input_args)
print(input_args)
print(args2)

input_args = ["pull"]
args3 = parser.parse_args(input_args)
print(input_args)
print(args3)

input_args = ["status"]
args4 = parser.parse_args(input_args)
print(input_args)
print(args4)

input_args = ["branch"]
args4 = parser.parse_args(input_args)
print(input_args)
print(args4)

input_args = ["nonexistent"]
args4 = parser.parse_args(input_args)
print(input_args)
print(args4)
