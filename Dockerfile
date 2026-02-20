FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

RUN mkdir -p data/logs uploads

EXPOSE 9000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import httpx; r = httpx.get('http://localhost:9000/api/health'); r.raise_for_status()"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9000"]
