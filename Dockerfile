FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY sf_apartment_aggregator ./sf_apartment_aggregator
COPY config.yaml ./config.yaml

RUN pip install --no-cache-dir .

CMD ["sf-apt", "poll", "--config", "config.yaml"]
