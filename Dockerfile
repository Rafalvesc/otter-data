FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.lock pyproject.toml ./
COPY backend ./backend
COPY scripts ./scripts
COPY examples ./examples
COPY frontend ./frontend
RUN pip install --no-cache-dir -c requirements.lock . \
    && pip check \
    && useradd --create-home --uid 10001 datapilot
USER datapilot
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
