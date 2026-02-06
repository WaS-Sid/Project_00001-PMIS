FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml poetry.lock* /app/
RUN pip install --no-cache-dir "poetry>=1.4"
RUN poetry config virtualenvs.create false && poetry install --no-dev --no-interaction
COPY app /app/app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
