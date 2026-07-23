# Makefile for Agent Environment

IMAGE_NAME = agent-environment
VERSION = 1.2.5
GHCR_REPO = ghcr.io/scaleapi/mcp-atlas

.PHONY: build run run-docker shell test run-mcp-completion push

run-docker: # run docker container for mcp servers (agent-environment service)
	docker run --rm -p 1984:1984 --env-file .env $(IMAGE_NAME):latest

build: # builds agent-environment
	cd services/agent-environment && docker buildx build --platform linux/amd64 -t $(IMAGE_NAME) .
	docker tag $(IMAGE_NAME):latest $(IMAGE_NAME):$(VERSION)

shell: # shell for agent-environment
	docker run -it --rm --env-file .env $(IMAGE_NAME):latest bash


# Makefile for MCP Eval

# Run the MCP completion server (port 3000, http post endpoint at /v2/mcp_eval/run_agent)
# Note: This runs agent completions (not evaluation/scoring). For scoring, see mcp_evals_scores.py
run-mcp-completion: 
	cd services/mcp_eval && uv run python -m mcp_completion.main

# Build and push multi-arch image to ghcr.io
# Requires Docker, and may not work with Rancher Desktop
# First do: docker login ghcr.io
push:
	@echo "--- Building and pushing multi-arch $(GHCR_REPO):$(VERSION) and :latest ---"
	cd services/agent-environment && docker buildx build --platform linux/amd64,linux/arm64 \
		-t $(GHCR_REPO):$(VERSION) \
		-t $(GHCR_REPO):latest \
		--push .
	@echo "✓ Successfully pushed to $(GHCR_REPO):$(VERSION)"