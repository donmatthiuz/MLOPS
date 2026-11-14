FROM python:3.12-slim AS production
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY src ./src
COPY api ./api
COPY tests/fixtures ./tests/fixtures
RUN pip install --no-cache-dir .
EXPOSE 8000
CMD ["uvicorn", "api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM production AS test
COPY tests ./tests
RUN pip install --no-cache-dir '.[dev]'
CMD ["pytest", "-q"]
