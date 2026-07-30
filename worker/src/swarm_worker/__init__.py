from importlib.metadata import PackageNotFoundError, version


def worker_version() -> str:
    try:
        return version("invariance-swarm-worker")
    except PackageNotFoundError:
        return "0.0.0+uninstalled"


__version__ = worker_version()
