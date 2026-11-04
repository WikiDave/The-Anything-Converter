FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg imagemagick ghostscript poppler-utils pandoc \
        libreoffice-writer libreoffice-calc libreoffice-impress fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV HOST=0.0.0.0 PORT=8000
EXPOSE 8000
CMD ["python", "app.py"]
