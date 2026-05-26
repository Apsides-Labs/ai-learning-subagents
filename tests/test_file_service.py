"""Atomic write semantics: target file appears all-or-nothing, never half-written."""

import os
from pathlib import Path

import pytest


async def test_atomic_write_text_writes_content(tmp_path: Path):
    from services.file_service import atomic_write_text

    target = tmp_path / "out.txt"
    await atomic_write_text(target, "hello world")

    assert target.read_text(encoding="utf-8") == "hello world"


async def test_atomic_write_text_creates_parent_dirs(tmp_path: Path):
    from services.file_service import atomic_write_text

    target = tmp_path / "nested" / "deep" / "out.txt"
    await atomic_write_text(target, "hello")

    assert target.read_text(encoding="utf-8") == "hello"


async def test_atomic_write_text_does_not_leave_tmp_file_on_success(tmp_path: Path):
    from services.file_service import atomic_write_text

    target = tmp_path / "out.txt"
    await atomic_write_text(target, "hello")

    siblings = list(tmp_path.iterdir())
    # Only the target file should exist; no leftover .tmp file.
    assert siblings == [target]


async def test_atomic_write_text_overwrites_existing(tmp_path: Path):
    from services.file_service import atomic_write_text

    target = tmp_path / "out.txt"
    target.write_text("old content")
    await atomic_write_text(target, "new content")

    assert target.read_text(encoding="utf-8") == "new content"
