import sys
sys.path.insert(0, '/app')
import uvicorn
uvicorn.run('main:app', host='0.0.0.0', port=8000)
