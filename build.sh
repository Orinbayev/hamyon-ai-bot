#!/usr/bin/env bash
# Render build script — web service tomonidan ishga tushiriladi
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input

python manage.py migrate
