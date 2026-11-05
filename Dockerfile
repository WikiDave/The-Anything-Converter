# Anything Converter in Docker: the web interface (default) and the terminal version.
#   web:       docker run -p 8000:8000 ghcr.io/wikidave/the-anything-converter
#   terminal:  docker run -it --rm -v "$PWD:/data" ghcr.io/wikidave/the-anything-converter anything-converter-tui
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg imagemagick ghostscript poppler-utils pandoc 7zip xorriso \
        tesseract-ocr tesseract-ocr-eng tesseract-ocr-nld tesseract-ocr-deu tesseract-ocr-fra \
        libreoffice-writer libreoffice-calc libreoffice-impress libreoffice-draw fonts-dejavu \
        graphviz qemu-utils fluidsynth fluid-soundfont-gm mame-tools smartmontools \
    && rm -rf /var/lib/apt/lists/*

# Deno: JavaScript runtime that yt-dlp needs for YouTube
COPY --from=denoland/deno:bin-2.1.4 /deno /usr/local/bin/deno

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# 'anything-converter-tui' works inside the container, also via 'docker exec -it' or over SSH
RUN printf '#!/bin/sh\nexec python /app/tui.py "$@"\n' > /usr/local/bin/anything-converter-tui \
    && chmod +x /usr/local/bin/anything-converter-tui \
    && mkdir -p /data /tmp/home && chmod 777 /data /tmp/home

# Works as any user (docker run --user "$(id -u):$(id -g)" keeps your file ownership)
ENV HOST=0.0.0.0 PORT=8000 HOME=/tmp/home COLORTERM=truecolor LANG=C.UTF-8 PYTHONUNBUFFERED=1
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/ping')" || exit 1
CMD ["python", "app.py"]
