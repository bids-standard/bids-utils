"""CLI command: bids-utils completion."""

from __future__ import annotations

import os
import sys

import click

from bids_utils.cli import main

# Click 8.0+ shell completion activation scripts.
# These set the environment variable that Click uses to trigger completion.
_ACTIVATION_SCRIPTS: dict[str, str] = {
    "bash": """\
eval "$(_BIDS_UTILS_COMPLETE=bash_source bids-utils)"
""",
    "zsh": """\
eval "$(_BIDS_UTILS_COMPLETE=zsh_source bids-utils)"
""",
    "fish": """\
_BIDS_UTILS_COMPLETE=fish_source bids-utils | source
""",
}

_SUPPORTED_SHELLS = tuple(_ACTIVATION_SCRIPTS)


def _detect_shell() -> str | None:
    """Detect the current shell from ``$SHELL``.

    Returns the shell base name (``bash``, ``zsh``, ``fish``) or ``None``
    if the shell cannot be determined or is unsupported.
    """
    shell_env = os.environ.get("SHELL", "")
    if not shell_env:
        return None
    shell_name = os.path.basename(shell_env)
    if shell_name in _SUPPORTED_SHELLS:
        return shell_name
    return None


@main.command()
@click.argument("shell", required=False, type=click.Choice(_SUPPORTED_SHELLS))
def completion(shell: str | None) -> None:
    """Output shell completion activation script.

    Auto-detects shell from $SHELL when SHELL argument is omitted.
    Supported shells: bash, zsh, fish.

    \b
    Usage:
      eval "$(bids-utils completion bash)"
      bids-utils completion >> ~/.bashrc
    """
    if shell is None:
        shell = _detect_shell()
        if shell is None:
            click.echo(
                "Error: Cannot detect shell from $SHELL. "
                f"Please specify one of: {', '.join(_SUPPORTED_SHELLS)}",
                err=True,
            )
            sys.exit(1)

    click.echo(_ACTIVATION_SCRIPTS[shell], nl=False)
