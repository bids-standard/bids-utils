"""bids-utils: CLI and Python library for manipulating BIDS datasets."""

try:
    from importlib.metadata import version

    __version__ = version("bids-utils")
except Exception:
    __version__ = "0+unknown"

from bids_utils._dataset import BIDSDataset

__all__ = ["BIDSDataset", "__version__"]
