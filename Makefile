PYTHON ?= python3
VENV := .venv
BIN := $(VENV)/bin
HEADLESS := SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy

.PHONY: install run demo test smoke screenshot clean

install:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install -r requirements-dev.txt

run:
	$(BIN)/python -m tetris

demo:
	$(BIN)/python -m tetris --autoplay

test:
	$(BIN)/python -m pytest

smoke:
	$(HEADLESS) $(BIN)/python -m tetris --autoplay --frames 300 --highscores /tmp/tetris-smoke.json

screenshot:
	$(BIN)/python scripts/screenshot.py

clean:
	find . -path ./$(VENV) -prune -o -name __pycache__ -type d -exec rm -rf {} +
	rm -rf .pytest_cache
