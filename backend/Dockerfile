# Cloud Run image for the FastAPI backend
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
WORKDIR /app
# Tesseract for OCR of scanned PDFs/photos (English; add tesseract-ocr-hin etc. for Indian languages)
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
