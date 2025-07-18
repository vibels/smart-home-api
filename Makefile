.PHONY: help install run build-linux build-windows setup-buildx test-setup test-run test-teardown test docker-test stop-all stop-influxdb stop-dashboard push-dockerhub

PYTHON := python
PIP := pip
DOCKER := docker
IMAGE_NAME := smart-home-dashboard
BUILDER_NAME := multiplatform-builder
IMAGE_TAG ?= latest

help:
	@echo "Available targets:"
	@echo "  install            - Install Python dependencies"
	@echo "  run                - Run the full stack with docker-compose"
	@echo "  build-linux        - Build for Linux (AMD64 + ARM64)"
	@echo "  build-windows      - Build for Windows (AMD64)"
	@echo "  test               - Run integration tests locally"
	@echo "  docker-test        - Run tests in Docker"
	@echo "  stop-all           - Stop all running containers"
	@echo "  stop-influxdb      - Stop InfluxDB container"
	@echo "  stop-dashboard     - Stop dashboard container"
	@echo "  push-dockerhub     - Push image to Docker Hub (interactive)"

install:
	$(PIP) install -r requirements.txt

run:
	docker compose up --pull always

build-linux: setup-buildx
	$(DOCKER) buildx build \
		--platform linux/amd64,linux/arm64 \
		--tag $(IMAGE_NAME):linux \
		--load \
		-f Dockerfile.dashboard \
		.

build-windows: setup-buildx
	$(DOCKER) buildx build \
		--platform windows/amd64 \
		--tag $(IMAGE_NAME):windows \
		--load \
		-f Dockerfile.dashboard \
		.

setup-buildx:
	$(DOCKER) buildx create --name $(BUILDER_NAME) --use --bootstrap || true
	$(DOCKER) buildx inspect --bootstrap

test-setup: install
	$(DOCKER) compose -f docker-compose.test.yml up -d
	@echo "Waiting for services to be ready..."
	@sleep 10

test-run:
	$(PYTHON) -m pytest tests/ -v

test-teardown:
	$(DOCKER) compose -f docker-compose.test.yml down -v

test: test-setup test-run test-teardown

docker-test:
	$(DOCKER) compose -f docker-compose.test.yml up --build --abort-on-container-exit
	$(DOCKER) compose -f docker-compose.test.yml down -v

clean:
	@rm -f temperature_data.db
	@rm -rf __pycache__
	@rm -rf .pytest_cache
	@rm -f *.pyc
	$(DOCKER) buildx rm $(BUILDER_NAME) 2>/dev/null || true

stop-all:
	$(DOCKER) compose stop

stop-influxdb:
	$(DOCKER) compose stop influxdb

stop-dashboard:
	$(DOCKER) compose stop dashboard

push-dockerhub:
	@read -p "Enter Docker Hub username: " username; \
	read -p "Enter local image name (e.g., $(IMAGE_NAME):arm64): " localimage; \
	read -p "Enter Docker Hub image tag (default: latest): " tag; \
	tag=$${tag:-latest}; \
	imagename=$$(echo $$localimage | cut -d':' -f1); \
	$(DOCKER) tag $$localimage $$username/$$imagename:$$tag; \
	$(DOCKER) push $$username/$$imagename:$$tag