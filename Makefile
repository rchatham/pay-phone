.PHONY: help venv setup run run-simulator run-simulator-silent test test-unit test-integration test-coverage test-watch clean clean-all install deploy ssh sync-secrets pi-status pi-logs pi-restart setup-secrets lint docs quickstart

# Default target
.DEFAULT_GOAL := help

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m # No Color

# Virtual environment
VENV_DIR := venv
PYTHON := $(VENV_DIR)/bin/python3
PIP := $(VENV_DIR)/bin/pip

##@ General

help: ## Display this help message
	@echo "$(BLUE)Payphone Project - Available Commands$(NC)"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"; printf "Usage:\n  make $(GREEN)<target>$(NC)\n"} /^[a-zA-Z_0-9-]+:.*?##/ { printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2 } /^##@/ { printf "\n$(BLUE)%s$(NC)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Local Development

venv: ## Create virtual environment (if not exists)
	@if [ ! -d "$(VENV_DIR)" ]; then \
		echo "$(BLUE)Creating virtual environment...$(NC)"; \
		python3 -m venv $(VENV_DIR); \
		echo "$(GREEN)✓ Virtual environment created$(NC)"; \
	else \
		echo "$(YELLOW)Virtual environment already exists$(NC)"; \
	fi

setup: venv ## Setup project (create venv and install dependencies)
	@echo "$(BLUE)Installing dependencies...$(NC)"
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt
	@echo "$(GREEN)✓ Setup complete$(NC)"
	@echo ""
	@echo "$(YELLOW)To activate the virtual environment:$(NC)"
	@echo "  source $(VENV_DIR)/bin/activate"

install: setup ## Alias for 'setup'

run: venv ## Run main payphone app locally (with mocked hardware)
	@echo "$(BLUE)Starting payphone (local mode)...$(NC)"
	@echo "$(YELLOW)Note: Hardware is mocked for local development$(NC)"
	$(PYTHON) -m payphone.main

run-simulator: venv ## Run interactive BIOS simulator
	@echo "$(BLUE)Starting BIOS simulator...$(NC)"
	$(PYTHON) test_phone_tree.py

run-simulator-silent: venv ## Run BIOS simulator in silent mode (no audio)
	@echo "$(BLUE)Starting BIOS simulator (silent)...$(NC)"
	echo "4\ny" | $(PYTHON) test_phone_tree.py

test: venv ## Run unit tests locally (no hardware required)
	@echo "$(BLUE)Running unit tests...$(NC)"
	$(PYTHON) -m pytest tests/unit -v

test-unit: test ## Alias for 'test'

test-integration: venv ## Run integration tests locally
	@echo "$(BLUE)Running integration tests...$(NC)"
	$(PYTHON) -m pytest tests/integration -v

test-coverage: venv ## Run tests with coverage report
	@echo "$(BLUE)Running tests with coverage...$(NC)"
	$(PYTHON) -m pytest --cov=payphone --cov-report=html --cov-report=term-missing

test-watch: venv ## Run tests in watch mode (requires pytest-watch)
	@echo "$(BLUE)Running tests in watch mode...$(NC)"
	@echo "$(YELLOW)Press Ctrl+C to stop$(NC)"
	$(VENV_DIR)/bin/ptw -- -v

clean: ## Clean generated files (cache, coverage, etc.)
	@echo "$(BLUE)Cleaning generated files...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov .coverage .coverage.* 2>/dev/null || true
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

clean-all: clean ## Clean everything including venv
	@echo "$(BLUE)Removing virtual environment...$(NC)"
	rm -rf $(VENV_DIR)
	@echo "$(GREEN)✓ Full cleanup complete$(NC)"

lint: venv ## Run code linting (requires pylint/flake8)
	@echo "$(BLUE)Running linters...$(NC)"
	@if [ -f "$(VENV_DIR)/bin/pylint" ]; then \
		$(VENV_DIR)/bin/pylint payphone/; \
	elif command -v pylint >/dev/null 2>&1; then \
		pylint payphone/; \
	else \
		echo "$(YELLOW)pylint not installed, skipping$(NC)"; \
	fi
	@if [ -f "$(VENV_DIR)/bin/flake8" ]; then \
		$(VENV_DIR)/bin/flake8 payphone/; \
	elif command -v flake8 >/dev/null 2>&1; then \
		flake8 payphone/; \
	else \
		echo "$(YELLOW)flake8 not installed, skipping$(NC)"; \
	fi

##@ Secrets Management

setup-secrets: ## Setup 1Password and load secrets (interactive)
	@echo "$(BLUE)Setting up 1Password integration...$(NC)"
	@echo ""
	@echo "1. Install 1Password CLI if not already installed:"
	@echo "   https://developer.1password.com/docs/cli/get-started/"
	@echo ""
	@echo "2. Sign in to 1Password:"
	@echo "   eval \$$(op signin)"
	@echo ""
	@echo "3. Create items in 1Password:"
	@echo "   - Item: 'Payphone-Pi' in 'Personal' vault"
	@echo "     Fields: username, password, host, port"
	@echo "   - Item: 'Payphone-APIs' in 'Personal' vault (optional)"
	@echo "     Fields: OpenAI/api_key, Twilio/account_sid, etc."
	@echo ""
	@echo "4. Load secrets:"
	@echo "   source scripts/load_secrets.sh"
	@echo ""
	@echo "See docs/SECRETS_MANAGEMENT.md for detailed instructions"

load-secrets: ## Load secrets from 1Password (must be sourced)
	@echo "$(YELLOW)Note: This command must be sourced to work:$(NC)"
	@echo "  source scripts/load_secrets.sh"
	@echo "Or add to your shell:"
	@echo "  alias load-secrets='source scripts/load_secrets.sh'"

##@ Raspberry Pi - Deployment

deploy: ## Deploy code to Raspberry Pi (requires loaded secrets)
	@echo "$(BLUE)Deploying to Raspberry Pi...$(NC)"
	@if [ -z "$$PI_HOST" ]; then \
		echo "$(YELLOW)Secrets not loaded. Loading now...$(NC)"; \
		bash -c "source scripts/load_secrets.sh && ./scripts/deploy_to_pi.sh"; \
	else \
		./scripts/deploy_to_pi.sh; \
	fi

deploy-full: ## Full deployment with dependency installation
	@echo "$(BLUE)Full deployment to Raspberry Pi...$(NC)"
	@if [ -z "$$PI_HOST" ]; then \
		echo "$(YELLOW)Secrets not loaded. Loading now...$(NC)"; \
		bash -c "source scripts/load_secrets.sh && ./scripts/deploy_to_pi.sh --full"; \
	else \
		./scripts/deploy_to_pi.sh --full; \
	fi

sync-secrets: ## Sync only secrets/config to Pi (no code)
	@echo "$(BLUE)Syncing secrets to Raspberry Pi...$(NC)"
	@if [ -z "$$PI_HOST" ]; then \
		bash -c "source scripts/load_secrets.sh && ./scripts/sync_config.sh"; \
	else \
		./scripts/sync_config.sh; \
	fi

##@ Raspberry Pi - Access

ssh: ## SSH into Raspberry Pi
	@if [ -z "$$PI_HOST" ]; then \
		bash -c "source scripts/load_secrets.sh && ./scripts/ssh_to_pi.sh"; \
	else \
		./scripts/ssh_to_pi.sh; \
	fi

pi-status: ## Check payphone service status on Pi
	@echo "$(BLUE)Checking service status...$(NC)"
	@if [ -z "$$PI_HOST" ]; then \
		bash -c "source scripts/load_secrets.sh && ./scripts/ssh_to_pi.sh 'sudo systemctl status payphone.service'"; \
	else \
		./scripts/ssh_to_pi.sh 'sudo systemctl status payphone.service'; \
	fi

pi-logs: ## View payphone logs on Pi (follow mode)
	@echo "$(BLUE)Viewing logs (Ctrl+C to exit)...$(NC)"
	@if [ -z "$$PI_HOST" ]; then \
		bash -c "source scripts/load_secrets.sh && ./scripts/ssh_to_pi.sh 'sudo journalctl -u payphone.service -f'"; \
	else \
		./scripts/ssh_to_pi.sh 'sudo journalctl -u payphone.service -f'; \
	fi

pi-restart: ## Restart payphone service on Pi
	@echo "$(BLUE)Restarting service...$(NC)"
	@if [ -z "$$PI_HOST" ]; then \
		bash -c "source scripts/load_secrets.sh && ./scripts/ssh_to_pi.sh 'sudo systemctl restart payphone.service'"; \
	else \
		./scripts/ssh_to_pi.sh 'sudo systemctl restart payphone.service'; \
	fi
	@sleep 2
	@echo "$(GREEN)Checking status...$(NC)"
	@make pi-status

pi-stop: ## Stop payphone service on Pi
	@echo "$(BLUE)Stopping service...$(NC)"
	@if [ -z "$$PI_HOST" ]; then \
		bash -c "source scripts/load_secrets.sh && ./scripts/ssh_to_pi.sh 'sudo systemctl stop payphone.service'"; \
	else \
		./scripts/ssh_to_pi.sh 'sudo systemctl stop payphone.service'; \
	fi

##@ Raspberry Pi - Testing

pi-test: ## Run all tests on Raspberry Pi
	@echo "$(BLUE)Running tests on Raspberry Pi...$(NC)"
	@if [ -z "$$PI_HOST" ]; then \
		bash -c "source scripts/load_secrets.sh && ./scripts/run_remote_tests.sh"; \
	else \
		./scripts/run_remote_tests.sh; \
	fi

pi-test-unit: ## Run unit tests on Pi
	@if [ -z "$$PI_HOST" ]; then \
		bash -c "source scripts/load_secrets.sh && ./scripts/run_remote_tests.sh --unit"; \
	else \
		./scripts/run_remote_tests.sh --unit; \
	fi

pi-test-hardware: ## Run hardware tests on Pi (requires actual hardware)
	@if [ -z "$$PI_HOST" ]; then \
		bash -c "source scripts/load_secrets.sh && ./scripts/run_remote_tests.sh --hardware"; \
	else \
		./scripts/run_remote_tests.sh --hardware; \
	fi

pi-test-gpio: ## Run GPIO tests on Pi
	@if [ -z "$$PI_HOST" ]; then \
		bash -c "source scripts/load_secrets.sh && ./scripts/run_remote_tests.sh --gpio"; \
	else \
		./scripts/run_remote_tests.sh --gpio; \
	fi

pi-test-coverage: ## Run tests with coverage on Pi
	@if [ -z "$$PI_HOST" ]; then \
		bash -c "source scripts/load_secrets.sh && ./scripts/run_remote_tests.sh --coverage"; \
	else \
		./scripts/run_remote_tests.sh --coverage; \
	fi

##@ Documentation

docs: ## Open documentation in browser
	@echo "$(BLUE)Opening documentation...$(NC)"
	@echo "Main docs:"
	@echo "  - WALKTHROUGH: docs/WALKTHROUGH.md"
	@echo "  - DEVELOPMENT: docs/DEVELOPMENT.md"
	@echo "  - BEST_PRACTICES: docs/BEST_PRACTICES.md"
	@echo "  - SD_CARD_SETUP: docs/SD_CARD_SETUP.md"
	@echo "  - SECRETS_MANAGEMENT: docs/SECRETS_MANAGEMENT.md"

##@ Quick Start

quickstart: ## Quick start guide for new developers
	@echo "$(BLUE)================================================$(NC)"
	@echo "$(BLUE)Payphone Project - Quick Start Guide$(NC)"
	@echo "$(BLUE)================================================$(NC)"
	@echo ""
	@echo "$(GREEN)1. Setup project (creates venv + installs deps):$(NC)"
	@echo "   make setup"
	@echo ""
	@echo "$(GREEN)2. Run local tests:$(NC)"
	@echo "   make test"
	@echo ""
	@echo "$(GREEN)3. Launch BIOS simulator:$(NC)"
	@echo "   make run-simulator"
	@echo ""
	@echo "$(GREEN)4. Setup 1Password secrets (for Pi deployment):$(NC)"
	@echo "   make setup-secrets"
	@echo "   source scripts/load_secrets.sh"
	@echo ""
	@echo "$(GREEN)5. Deploy to Raspberry Pi:$(NC)"
	@echo "   make deploy-full"
	@echo ""
	@echo "$(GREEN)6. Check status:$(NC)"
	@echo "   make pi-status"
	@echo ""
	@echo "$(GREEN)7. View logs:$(NC)"
	@echo "   make pi-logs"
	@echo ""
	@echo "For detailed documentation, see:"
	@echo "  - docs/WALKTHROUGH.md - Complete tutorial"
	@echo "  - docs/DEVELOPMENT.md - Development guide"
	@echo "  - make help - All available commands"
	@echo ""
