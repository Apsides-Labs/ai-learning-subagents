.PHONY: install test setup weekly article measure validate

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

measure:
	uv run python main.py --mode measure

validate:
	uv run python main.py --mode validate
