PYTHON = python3
VENV = .venv

DEV_DIR = developer
CLIENT_DIR = client

DEV_ENTRY = developer_client.py
CLIENT_ENTRY = lobby_client.py

REQ = requirements.txt

# 偵測平台，決定虛擬環境路徑
ifeq ($(OS),Windows_NT)
    PIP = $(VENV)/Scripts/pip.exe
    PYTHON_VENV = $(VENV)/Scripts/python.exe
else
    PIP = $(VENV)/bin/pip
    PYTHON_VENV = $(VENV)/bin/python
endif

.PHONY: help setup developer client clean

help:
	@echo "Available targets:"
	@echo "  make setup     - create venv & install deps"
	@echo "  make developer - run developer"
	@echo "  make client    - run client"
	@echo "  make clean     - remove venv"

setup:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install -r $(REQ)

developer:
	$(PYTHON_VENV) $(DEV_DIR)/$(DEV_ENTRY)

client:
	$(PYTHON_VENV) $(CLIENT_DIR)/$(CLIENT_ENTRY)

clean:
ifeq ($(OS),Windows_NT)
	rmdir /S /Q $(VENV)
else
	rm -rf $(VENV)
endif