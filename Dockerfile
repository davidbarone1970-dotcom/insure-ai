FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi==0.115.0 uvicorn[standard]==0.30.6 sqlalchemy[asyncio]==2.0.35 asyncpg==0.29.0 anthropic==0.34.0 pydantic==2.8.2 pydantic-settings==2.4.0 python-dotenv==1.0.1 httpx==0.27.2
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
