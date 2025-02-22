FROM python:3.11-slim AS builder

LABEL authors="octavio@msk.ai"
# ENVIRONMENT CONFIGURATION
ARG USER_ID
ARG GROUP_ID
# create the appropriate directories
ENV APP_HOME=/home/app/web
# standardised caching dir for applications
ENV XDG_CACHE_HOME=/home/app/.cache



RUN mkdir -p $APP_HOME
RUN mkdir -p $APP_HOME/staticfiles && mkdir -p $APP_HOME/media && mkdir -p $APP_HOME/logging


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
    awscli

RUN ARCH=$(dpkg --print-architecture) && \
    case $ARCH in \
        amd64) URL="https://s3.amazonaws.com/session-manager-downloads/plugin/latest/ubuntu_64bit/session-manager-plugin.deb" ;; \
        i386) URL="https://s3.amazonaws.com/session-manager-downloads/plugin/latest/ubuntu_32bit/session-manager-plugin.deb" ;; \
        arm64) URL="https://s3.amazonaws.com/session-manager-downloads/plugin/latest/ubuntu_arm64/session-manager-plugin.deb" ;; \
        *) echo "Unsupported architecture" && exit 1 ;; \
    esac && \
    curl "$URL" -o "session-manager-plugin.deb" && \
    dpkg -i session-manager-plugin.deb

RUN rm -rf /var/lib/apt/lists/* && \
    mkdir -p /var/log/supervisor && \
    pip install --no-cache-dir --upgrade pip

# USER & GROUP SETUP
RUN addgroup --system app && adduser --system app --ingroup app

RUN useradd -r -g app gunicorn && \
    useradd -r -g app worker && \
    useradd -r -g app flower && \
    git config --global --add safe.directory /app && \
    mkdir -p /home/app/.cache && \
    mkdir -p /nonexistent



# If USER_ID and GROUP_ID are provided, adjust the created user and group
# To avoid perms on linux being set to root when chowning if :z is set.
RUN if [ -n "$USER_ID" ] && [ -n "$GROUP_ID" ]; then \
        usermod -u $USER_ID app && \
        groupmod -g $GROUP_ID app; \
    fi

COPY docker/wait-for-it.sh /usr/bin/wait-for-it.sh

RUN chown -R app:app $APP_HOME && \
    chmod -R u+rw $APP_HOME && \
    chmod +x /usr/bin/wait-for-it.sh && \
    chown -R app:app /home/app/.cache && \
    chown -R app:app /tmp  && \
    chown -R app:app /nonexistent && \
    chown -R app:app /usr/bin/wait-for-it.sh

# DEP INSTALLATION
WORKDIR $APP_HOME
# set safe directories for pre-commit
RUN git config --global --add safe.directory /app

ADD . $APP_HOME

USER app
