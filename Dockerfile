# Kennisbank – productie-image.
# Bouwen:   docker build -t kennisbank:1.1.0 .
# Eigen (goedgekeurde) basis-image gebruiken:  --build-arg BASE_IMAGE=<registry>/python:3.13-slim
ARG BASE_IMAGE=python:3.13-slim-bookworm

FROM ${BASE_IMAGE} AS bouw
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt .
RUN python -m venv /opt/venv && /opt/venv/bin/pip install -r requirements.txt
COPY . .
# Bestanden die op Windows zijn uitgepakt: regeleinden en uitvoerrecht van het startscript herstellen
RUN sed -i 's/\r$//' docker/entrypoint.sh && chmod 755 docker/entrypoint.sh
RUN KB_DEBUG=0 KB_SECRET_KEY=alleen-tijdens-bouwen /opt/venv/bin/python manage.py collectstatic --noinput \
 && rm -rf .venv .git kennisbank/tests

FROM ${BASE_IMAGE}
LABEL org.opencontainers.image.title="Kennisbank" \
      org.opencontainers.image.description="Kennisbank voor werkinstructies, werkafspraken en processen" \
      org.opencontainers.image.licenses="EUPL-1.2" \
      org.opencontainers.image.version="1.1.0"
ENV PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN groupadd --system --gid 10001 kennisbank \
 && useradd --system --uid 10001 --gid kennisbank --home-dir /app --shell /usr/sbin/nologin kennisbank
COPY --from=bouw /opt/venv /opt/venv
COPY --from=bouw --chown=10001:10001 /app /app
WORKDIR /app
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status==200 else 1)"
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["web"]
