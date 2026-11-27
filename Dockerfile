FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /app
COPY requirements.txt ./
COPY backend ./backend
COPY frontend ./frontend
COPY assl ./assl
COPY web_generator ./web_generator
COPY quality_review ./quality_review
COPY requirements ./requirements
COPY constitution ./constitution
COPY references ./references
RUN useradd --create-home appuser && mkdir outputs && chmod -R a+rX /app && chown appuser:appuser outputs
RUN pip install --no-cache-dir -r requirements.txt && python -m pip check
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
