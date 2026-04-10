"""bids-utils CLI entry point."""

import click

from bids_utils import __version__


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="bids-utils")
def main() -> None:
    """CLI for manipulating BIDS datasets."""


# Import subcommand modules so they register with the click group.
# This must happen after `main` is defined.
from bids_utils.cli import (  # noqa: E402, F401
    completion,
    merge,
    metadata,
    migrate,
    rename,
    run,
    session,
    split,
    subject,
)
