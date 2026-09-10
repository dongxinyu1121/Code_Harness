"""CLI application entrypoint."""

from .config import build_arg_parser, load_local_env
from .factory import build_agent
from .repl import run


def main(argv=None):
    load_local_env()
    args = build_arg_parser().parse_args(argv)
    return run(build_agent(args), args)

