"""bids-utils CLI entry point."""

import click

from bids_utils import __version__


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="bids-utils")
def main() -> None:
    """CLI for manipulating BIDS datasets."""
