FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    make \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY src/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY deploy.sh ./

RUN mkdir -p /app/vaults

WORKDIR /app/src

RUN cd libvault && make

RUN groupadd -g 1000 ctf && useradd -r -u 1000 -g 1000 -s /bin/false ctf

EXPOSE 3333

ENV FLASK_APP=blastpass.py
ENV FLASK_ENV=production

RUN chmod +x /app/deploy.sh

CMD ["/app/deploy.sh"]
