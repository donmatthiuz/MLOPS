FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY config ./config
COPY datos ./datos
COPY tests ./tests

FROM python:3.12-slim AS production
WORKDIR /app
COPY --from=0 /app /app
RUN pip install --no-cache-dir .
EXPOSE 8000
CMD ["uvicorn", "gasolina_gt.serving.api:app", "--host", "0.0.0.0", "--port", "8000"]

FROM production AS test
RUN pip install --no-cache-dir '.[dev]'
CMD ["pytest", "-q"]
