from importlib import metadata

try:
    __version__ = metadata.version(__package__)
except metadata.PackageNotFoundError:
    # Case where package metadata is not available, default to a 'non-outdated' version.
    # Ref: config.py::load_settings()
    __version__ = "2.6.3"
