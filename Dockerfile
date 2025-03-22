FROM python:3.11-slim AS base

LABEL authors="mail@octavio.sh"

# standardised caching dir for applications

# INSTALL DEBIAN DEPS
# Fix hash sum mismatch errors, https://serverfault.com/questions/722893/debian-mirror-hash-sum-mismatch/743015
RUN echo "Acquire::http::Pipeline-Depth 0;\nAcquire::http::No-Cache true;\nAcquire::BrokenProxy true;\n" > /etc/apt/apt.conf.d/99fixbadproxy
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    libpq-dev \
    gettext-base \
    gettext \
    bash \
    supervisor \
    python3 \
    libmagic1 \
    libglib2.0-dev \
    postgresql \
    postgresql-contrib \
    postgresql-client \
    libpango1.0-dev \
    libpq-dev \
    make \
    gcc \
    awscli \
    build-essential

RUN pip install poetry && pip install --no-cache-dir poetry &&  poetry config virtualenvs.create false

COPY wait-for-it.sh /usr/bin/wait-for-it.sh

RUN chmod +x /usr/bin/wait-for-it.sh

FROM base AS base_dev
ARG UID
ARG GID
# USER & GROUP SETUP
ENV USER_NAME app
ENV USER_HOME /home/$USER_NAME
ENV APP_HOME $USER_HOME/src



RUN \
    # Set default names for group and user
    GROUP_NAME="app" && \
    USER_NAME="app" && \
    # Check and set/create group
    if getent group ${GID} > /dev/null 2>&1; then \
        GROUP_NAME=$(getent group ${GID} | cut -d: -f1); \
    else \
        addgroup --gid ${GID} ${GROUP_NAME}; \
    fi && \
    # Check and set/create user
    if getent passwd ${UID} > /dev/null 2>&1; then \
        USER_NAME=$(getent passwd ${UID} | cut -d: -f1); \
    else \
        sed -i '/^UID_MIN/ s/1000/100/' /etc/login.defs && \
        adduser --uid ${UID} --gid ${GID} --disabled-password --gecos "" ${USER_NAME} && \
        sed -i '/^UID_MIN/ s/100/1000/' /etc/login.defs; \
    fi && \
    # Set up home directory with consistent ownership
    mkdir -p /home/${USER_NAME} && \
    chown ${USER_NAME}:${GROUP_NAME} /home/${USER_NAME}

WORKDIR $APP_HOME
ENV PYTHONUNBUFFERED=1
ENV PIP_ROOT_USER_ACTION=ignore
ARG POETRY_GROUPS

COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false && \
    poetry install --with="$POETRY_GROUPS" --no-interaction --no-ansi --no-root
# set safe directories for pre-commit
RUN git config --global --add safe.directory $APP_HOME

USER $USER_NAME

FROM base_dev as di_web

ENTRYPOINT ["/bin/sh", "-c", "exec ${APP_HOME}/entrypoint.sh \"$@\"", "--"]
CMD ["gunicorn", "config.wsgi:application", "--access-logfile", "-", "--workers", "4", "--bind", ":8000"]
