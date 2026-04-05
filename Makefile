.PHONY: lint format type-check test quality

lint:
	uv run ruff check .

format:
	uv run ruff format .

type-check:
	uv run ty check

test:
	uv run pytest

quality: lint type-check test
