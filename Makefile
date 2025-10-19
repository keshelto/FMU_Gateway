.PHONY: build run deploy

build:
	docker compose -f deploy/docker-compose.yml build

run:
	docker compose -f deploy/docker-compose.yml up

deploy:
	@echo "Deploy the private API by pushing Docker images and applying cloud configs."
