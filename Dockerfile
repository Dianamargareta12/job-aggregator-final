FROM php:8.2-cli-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Ekstensi PHP untuk koneksi MySQL dan runtime Python untuk scraper.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-venv \
        ca-certificates \
        curl \
    && docker-php-ext-install mysqli pdo pdo_mysql \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt

# Instal library Python dan Chromium beserta dependency Linux-nya.
RUN python3 -m pip install --no-cache-dir --break-system-packages -r /app/requirements.txt \
    && python3 -m playwright install --with-deps chromium

COPY . /app

RUN mkdir -p /app/data/raw /app/data/clean /app/data/rejected /app/storage \
    && chmod -R 775 /app/data /app/storage

EXPOSE 8080

# Railway menyediakan PORT secara otomatis.
CMD ["sh", "-c", "php -S 0.0.0.0:${PORT:-8080} -t /app/frontend"]
