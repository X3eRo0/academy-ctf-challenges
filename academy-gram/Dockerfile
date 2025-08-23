FROM python:3.10-slim

WORKDIR /app

COPY src .

RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn

RUN useradd -m -u 1001 academy && \
    chown -R academy:academy /app

USER academy

EXPOSE 2750
CMD ["./start.sh"]
