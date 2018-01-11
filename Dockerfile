FROM python:2.7-stretch

LABEL maintainer="Fabrice Baumann <fabrice.baumann@mindgeek.com>"

ADD . /octodns

RUN cd /octodns \
    && pip install -e . \
    && pip install -e ".[dev]" \
    && pip install -e ".[test]" \
    && rm -rf /var/lib/apt/lists/*
