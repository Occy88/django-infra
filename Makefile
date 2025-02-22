SHELL = /bin/sh
ENV_FILE = .env


ifeq ("$(wildcard $(ENV_FILE))","")
$(warning "Required environment variable file '$(ENV_FILE)' file not found in project directory.")
else
include $(ENV_FILE)
endif

.PHONY: help docker_build docker_up docker_down docker_bash show_changed_files hooks
.DEFAULT_GOAL: help
EXEC_PREFIX = docker exec -it dt_web
DOCKER_COMPOSE = docker compose


define HELP_TEXT
"\
The following make commands are available:\n\
- help              : This help text.\n\
- shell             : Create a local manage.py shell that is read only.\n\
- build             : Builds the docker images. \n\
- up                : runs docker-compose up. \n\
- down              : runs docker-compose down. \n\
- reload            : reloads web server \n\
- sh_web            : creates a bash shell on the web server, the container must be already running. \n\
- sh_db             : creates a bash shell on the db server, the container must be already running. \n\
- sh_redis          : creates a bash shell on the redis server, the container must be already running. \n\
- sh_celery         : creates a bash shell on the celery server, the container must be already running. \n\
- show_changed_files: Which files have been staged according to git. \n\
- hooks             : Setup pre-commit hooks. \n\
- pre-commit        : runs pre-commit routine. \n\
- test [TEST=]      : Test using keepdb, e.g.: \n\
- redoc-up          : Initialises the local redocly server - see Wiki for details \n\
\b                       \`make test TEST=chat.tests.test_utils.HasChatTestCase.test_returns_true_if_all_matches\`\n\
- debug [TEST=]     : Same as test but with interactive, so it works if you have something like this in the code: \n\
\b                       \`import code; code.interact(local=dict(globals(), **locals()))\` \n\
"
endef

help:
	@printf $(HELP_TEXT)

shell:
	@python manage.py shell_plus --settings=dt.read_only_settings


setup:
	@echo -e "$(INFO)Rebuilding docker$(COFF)"
	$(DOCKER_COMPOSE) down -v
ifeq ($(shell uname -s),Darwin)
	@echo -e "$(INFO)Running on macOS, skipping USER_ID and GROUP_ID setting"
	DOCKER_DEFAULT_PLATFORM=linux/arm64 $(DOCKER_COMPOSE) build $(cmd) --build-arg POETRY_GROUPS=dev,web,test
else
	@echo -e "$(INFO)Not running on macOS, setting USER_ID and GROUP_ID"
	$(DOCKER_COMPOSE) build $(cmd) --build-arg USER_ID=$(shell id -u) --build-arg GROUP_ID=$(shell id -g) --build-arg POETRY_GROUPS=dev,web,test
endif
	@make docker-up
	@echo -e "$(FORMAT)\n\n=============[$(BOLD)$(SUCCESS) SETUP SUCCEEDED $(FORMAT)]========================="
	@echo -e "$(INFO)Run 'make setup_data' to collect staticfiles.$(COFF)"
	@echo -e "$(INFO)Run 'make run cmd=< -d >' to start Django development server.$(COFF)"

docker-up:
	docker compose up -d

test:
	@echo -e "$(WARNING)===[ RESETTING test_default.psql wait for migrations to apply ]===$(COFF)"
	#git checkout origin/master docker/test_default.psql
	make set-test
	@make docker-up
	$(EXEC_PREFIX) python3 -m pytest --durations=30 --disable-warnings $(args) $(path) || exit 1

.env: .env-dev-example
	@if [ ! -f .env ]; then \
		echo -e "$(CYAN)Creating .env file$(COFF)"; \
		install -b --suffix=.bak -m 644 .env-dev-example .env; \
	else \
		echo -e "$(CYAN).env file already exists$(COFF)"; \
	fi

merge-env:
	if [ -z "$(file2)" ]; then \
		cp $(file1) .env; \
	else \
		cat $(file1) $(file2)  > .env; \
	fi

set-test:
	$(MAKE) merge-env file1=.env-dev-example file2=.env.test
