FROM python:3.11-slim AS builder

# Fix hash sum mismatch errors, https://serverfault.com/questions/722893/debian-mirror-hash-sum-mismatch/743015
RUN echo "Acquire::http::Pipeline-Depth 0;\nAcquire::http::No-Cache true;\nAcquire::BrokenProxy true;\n" > /etc/apt/apt.conf.d/99fixbadproxy
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    build-essential
ENV PYTHONUNBUFFERED 1
ENV PIP_ROOT_USER_ACTION=ignore
ARG POETRY_GROUPS
WORKDIR /app/web
ENV POETRY_VERSION=2.0.1
RUN pip install "poetry==$POETRY_VERSION"
RUN pip install --no-cache-dir poetry &&  poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock README.md ./

RUN poetry install --no-interaction --no-ansi --no-root

FROM di_base AS final
# Append the custom directory to PATH, ensuring original executables take priority
COPY --from=builder /usr/local/bin /usr/local/pybin
ENV PATH="${PATH}:/usr/local/pybin"
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
