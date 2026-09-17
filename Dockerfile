FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    BEP_DATA_DIR=/data

WORKDIR /app

COPY requirements.txt ./
# ifcopenshell ships manylinux wheels; libgomp is needed by its geometry kernel.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir -r requirements.txt

COPY . .
RUN pip install --no-cache-dir --no-deps -e .

# The Fly volume is mounted here; create it so the image also runs standalone.
RUN mkdir -p /data

EXPOSE 8080

# One worker keeps the SQLite file single-writer; threads carry the concurrency.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", \
     "--timeout", "60", "--access-logfile", "-", "wsgi:app"]
