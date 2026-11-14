# Hugging Face Spaces (Docker SDK) / Render / any container host. Port 7860 is the HF Spaces default.
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir numpy pandas pyarrow requests shapely fastapi uvicorn
COPY analog_atlas analog_atlas
COPY config config
COPY data data
ENV PORT=7860
CMD uvicorn analog_atlas.api:app --host 0.0.0.0 --port ${PORT}
