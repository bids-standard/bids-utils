"""bids-utils CLI entry point."""

import click

from bids_utils import __version__


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="bids-utils")
@click.option(
    "--annexed",
    type=click.Choice(["error", "get", "skip-warning", "skip"]),
    default=None,
    envvar="BIDS_UTILS_ANNEXED",
    help="How to handle git-annex files without local content.",
)
@click.pass_context
def main(ctx: click.Context, annexed: str | None) -> None:
    """CLI for manipulating BIDS datasets."""
    ctx.ensure_object(dict)
    ctx.obj["annexed"] = annexed or "error"


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
