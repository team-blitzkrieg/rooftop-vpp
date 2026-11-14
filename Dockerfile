FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements-serve.txt .
RUN pip install --no-cache-dir -r requirements-serve.txt

COPY forecasting ./forecasting
COPY data/__init__.py ./data/__init__.py
COPY data/pipeline ./data/pipeline
COPY serve ./serve
COPY migrations ./migrations

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app
EXPOSE 8000

CMD ["uvicorn", "serve.app:app", "--host", "0.0.0.0", "--port", "8000"]
