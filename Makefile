SRC = src
EXE = $(SRC)

VENV = .venv
PYTHON := $(VENV)/bin/python3.13

# ANSI codes
GREEN = \033[0;32m
RED = \033[0;31m
YELLOW = \033[0;33m
BOLD = \033[1m

SUCCESS = \033[1;92m
RESET = \033[0m

# Files to clean
TRASH = $(VENV) $(SRC)/__pycache__ $(SRC)/display/__pycache__ $(SRC)/entities/__pycache__ \
		$(SRC)/game/__pycache__ $(SRC)/overseer/__pycache__ __pycache__ .mypy_cache


install:
	@echo "$(BOLD)Initializing project environment:$(RESET)"

	@echo "$(YELLOW)Creating virtual environment...$(RESET)"
	@uv venv $(VENV) --clear > /dev/null 2>&1
	@echo "$(GREEN)Virtual environment setup complete$(RESET)\n"

	@echo "$(YELLOW)Installing dependencies...$(RESET)"
	@uv sync
	@echo "$(GREEN)All dependencies successfully installed$(RESET)"

	@echo "\n$(SUCCESS)Project can now be run safely!$(RESET)"


run:
	@uv run python -m $(EXE)


lint:
	@echo "$(BOLD)Verifying project source code:$(RESET)"

	@echo "$(YELLOW)Running flake8...$(RESET)"
	@$(PYTHON) -m flake8 --exclude=.venv
	@echo "$(GREEN)No norm errors found$(RESET)"

	@echo "\n$(YELLOW)Running mypy...$(RESET)"
	@$(PYTHON) -m mypy . $(MYPY_FLAGS)
	@echo "$(GREEN)No typing errors found$(RESET)"

	@echo "\n$(SUCCESS)Success: no errors found in source code!$(RESET)"


clean:
	@echo "$(YELLOW)Initiating cleanup operation...$(RESET)"
	@found=0; \
	for i in $(TRASH); do \
		if [ -d "$$i" ]; then \
			echo " - Removed directory $(RED)'$$i'$(RESET)"; \
			found=1; \
		elif [ -e "$$i" ]; then \
			echo " - Removed file $(RED)'$$i'$(RESET)"; \
			found=1; \
		fi; \
	done; \
	if [ $$found -eq 0 ]; then \
		echo "$(GREEN)Nothing to clean :)$(RESET)"; \
	fi
	@rm -rf $(TRASH)
	@echo "$(SUCCESS)\nCleanup complete!$(RESET)"
