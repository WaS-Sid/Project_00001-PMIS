FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml poetry.lock* /app/
RUN pip install --no-cache-dir "poetry>=1.4"
RUN poetry config virtualenvs.create false && poetry install --no-dev --no-interaction
COPY worker.py /app/worker.py
CMD ["celery", "-A", "worker.celery_app", "worker", "--loglevel=info"]
