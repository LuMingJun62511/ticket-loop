from cs_agent import __version__
from cs_agent.config import PATHS, SETTINGS


def test_version() -> None:
    assert __version__


def test_labels_are_sane() -> None:
    assert len(SETTINGS.labels) >= 2
    assert len(set(SETTINGS.labels)) == len(SETTINGS.labels)


def test_repo_root_exists() -> None:
    assert PATHS.root.is_dir()
