"""Smoke test: the package imports."""

import tst


def test_package_imports() -> None:
    assert tst.__doc__
