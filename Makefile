.PHONY: compile-deps setup clean-pyc clean-test clean-venv clean test mypy lint format check clean-example dev-env refresh-containers rebuild-images build-image push-image

# Module name - will be updated by init script
MODULE_NAME := mcp_filesystem

# Development Setup
#################
compile-deps:  # Compile dependencies from pyproject.toml
	uv pip compile pyproject.toml -o requirements.txt
	uv pip compile pyproject.toml --extra dev -o requirements-dev.txt

PYTHON_VERSION ?= 3.12

ensure-uv:  # Install uv if not present
	@which uv > /dev/null || (curl -LsSf https://astral.sh/uv/install.sh | sh)

setup: ensure-uv compile-deps ensure-scripts  # Install dependencies
	UV_PYTHON_VERSION=$(PYTHON_VERSION) uv venv
	UV_PYTHON_VERSION=$(PYTHON_VERSION) uv pip sync requirements.txt requirements-dev.txt
	$(MAKE) install-hooks

install-hooks:  # Install pre-commit hooks if in a git repo with hooks configured
	@if [ -d .git ] && [ -f .pre-commit-config.yaml ]; then \
		echo "Installing pre-commit hooks..."; \
		uv run pre-commit install; \
	fi

ensure-scripts:  # Ensure scripts directory exists and files are executable
	mkdir -p scripts
	chmod +x scripts/*.py

# Cleaning
#########
clean-pyc:  # Remove Python compilation artifacts
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

clean-test:  # Remove test and coverage artifacts
	rm -f .coverage
	rm -f .coverage.*

clean-venv:  # Remove virtual environment
	rm -rf .venv

clean: clean-pyc clean-test clean-venv

# Testing and Quality Checks
#########################
test: setup  # Run pytest with coverage
	uv run -m pytest tests --cov=$(MODULE_NAME) --cov-report=term-missing

mypy: setup  # Run type checking
	uv run -m mypy $(MODULE_NAME)

lint: setup  # Run ruff linter with auto-fix
	uv run -m ruff check --fix $(MODULE_NAME)

format: setup  # Run ruff formatter
	uv run -m ruff format $(MODULE_NAME)

check: setup lint format test mypy  # Run all quality checks

# Project Management
##################
clean-example:  # Remove example code (use this to start your own project)
	rm -rf src/example.py tests/test_example.py
	touch src/__init__.py tests/__init__.py

init: setup  # Initialize a new project
	uv run python scripts/init_project.py

# Docker
########
IMAGE_NAME = container-registry.io/python-collab-template
IMAGE_TAG = latest

dev-env: refresh-containers
	@echo "Spinning up a dev environment ."
	@docker compose -f docker/docker-compose.yml down
	@docker compose -f docker/docker-compose.yml up -d dev
	@docker exec -ti composed_dev /bin/bash

refresh-containers:
	@echo "Rebuilding containers..."
	@docker compose -f docker/docker-compose.yml build

rebuild-images:
	@echo "Rebuilding images with the --no-cache flag..."
	@docker compose -f docker/docker-compose.yml build --no-cache

build-image:
	@echo Building dev image and tagging as ${IMAGE_NAME}:${IMAGE_TAG}
	@docker compose -f docker/docker-compose.yml down
	@docker compose -f docker/docker-compose.yml up -d dev
	@docker tag dev ${IMAGE_NAME}:${IMAGE_TAG}

push-image: build-image
	@echo Pushing image to container registry
	@docker push ${IMAGE_NAME}:${IMAGE_TAG}
