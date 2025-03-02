FROM python:3.12-slim

# Install Auxiliary Software
RUN apt-get update && apt-get install -y \
    make \
    apt-utils \
    apt-transport-https \
    curl \
    gcc \
    gnupg \
    gnupg-agent \
    graphviz \
    software-properties-common \
    vim \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src

COPY pyproject.toml .
COPY README.md .
COPY src/ ./src/
COPY tests/ ./tests/

RUN pip install -U pip uv \
    && uv pip compile pyproject.toml -o requirements.txt \
    && uv pip compile pyproject.toml --extra dev -o requirements-dev.txt \
    && uv pip sync requirements.txt requirements-dev.txt

CMD ["/bin/bash"]
