FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

RUN groupadd --gid 10001 swarm \
    && useradd \
        --uid 10001 \
        --gid swarm \
        --create-home \
        --shell /usr/sbin/nologin \
        swarm

WORKDIR /app

COPY requirements.txt /app/requirements.txt

RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app

USER swarm

EXPOSE 8787

CMD [
  "uvicorn",
  "app.main:app",
  "--host",
  "0.0.0.0",
  "--port",
  "8787",
  "--proxy-headers"
]
