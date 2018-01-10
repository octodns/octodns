FROM python:2.7-slim-stretch

LABEL maintainer="Fabrice Baumann <fabrice.baumann@mindgeek.com>"

RUN apt-get update \
    && apt-get install -y \
        git \
        python-pip \
    && mkdir /octodns \
    && cd /octodns \
    && git clone https://github.com/MindGeekOSS/octodns.git . \
    && pip install -e . \
    && pip install -e ".[dev]" \
    && rm -rf /var/lib/apt/lists/*
