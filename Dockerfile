FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir gunicorn gevent

COPY app.py .
COPY templates/ templates/
COPY static/ static/

ENV DB_PATH=/data/counter.db
RUN mkdir -p /data

EXPOSE 5000

CMD ["gunicorn", "--worker-class", "gevent", "--workers", "1", \
     "--bind", "0.0.0.0:5000", "--access-logfile", "-", "app:app"]
