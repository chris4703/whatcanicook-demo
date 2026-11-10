FROM python:3.12-slim
WORKDIR /app
COPY app.py .
COPY static ./static
COPY scripts ./scripts
ENV PYTHONUNBUFFERED=1 HOST=0.0.0.0 PANTRY_DB=/data/pantry.sqlite OFF_DB=/data/openfoodfacts.sqlite
RUN useradd --uid 10001 --create-home pantry && mkdir /data && chown pantry:pantry /data
USER pantry
VOLUME /data
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/state', timeout=2)"
CMD ["python", "app.py"]
