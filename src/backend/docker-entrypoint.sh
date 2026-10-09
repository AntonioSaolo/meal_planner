#!/bin/sh
set -eu

export CREATE_DEFAULT_ADMIN="${CREATE_DEFAULT_ADMIN:-true}"
python seed_default_data.py
exec python main.py
