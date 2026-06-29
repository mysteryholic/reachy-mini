FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7860

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    git \
    libglib2.0-0 \
    libgl1 \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY index.html style.css ./

RUN python -m pip install --upgrade pip setuptools wheel \
    && pip install .

EXPOSE 7860

CMD ["bash", "-lc", "reachy-mini-daemon --sim >/tmp/reachy-mini-daemon.log 2>&1 & exec reachy-robotis --gradio"]
