FROM python:2.7-stretch

LABEL maintainer="Fabrice Baumann <fabrice.baumann@mindgeek.com>"

RUN pip install PyYaml>=3.12 \
    dnspython>=1.15.0 \
    futures>=3.1.1 \
    incf.countryutils>=1.0 \
    ipaddress>=1.0.18 \
    natsort>=5.0.3 \
    python-dateutil>=2.6.1 \
    requests>=2.13.0 \
    azure-mgmt-dns==1.0.1 \
    azure-common==1.1.6 \
    boto3>=1.4.6 \
    botocore>=1.6.8 \
    docutils>=0.14 \
    dyn>=1.8.0 \
    google-cloud>=0.27.0 \
    jmespath>=0.9.3 \
    msrestazure==0.4.10 \
    nsone>=0.9.14 \
    ovh>=0.4.7 \
    s3transfer>=0.1.10 \
    six>=1.10.0

ADD . /octodns
WORKDIR /octodns

RUN pip install -e . \
    && pip install -e ".[dev]" \
    && rm -rf /var/lib/apt/lists/*



