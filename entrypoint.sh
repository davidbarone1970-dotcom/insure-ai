#!/bin/sh
cd /app
python -c "import traceback; 
exec(open('main.py').read())" 2>&1 || true
uvicorn main:app --host 0.0.0.0 --port 8000
