#!/bin/bash
set -e
cd "$(dirname "$0")/.."
pytest tests/ -v --tb=short
