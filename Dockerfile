FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx openssl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt ansible-core>=2.16

COPY . .

RUN mkdir -p /tmp/reports /app/rag_data/pdfs /app/rag_data/chroma

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY start.sh /start.sh
RUN chmod +x /start.sh

EXPOSE 8080 9443

CMD ["/start.sh"]
