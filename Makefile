.PHONY: install test setup weekly article

install:
	uv sync

test:
	uv run pytest

setup:
	uv run python main.py --mode setup

weekly:
	uv run python main.py --mode weekly

article:
	uv run python main.py --mode article
