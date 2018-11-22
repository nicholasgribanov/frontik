FROM ubuntu:18.04

COPY . /tmp
WORKDIR /tmp

RUN apt-get update && apt-get install --no-install-recommends --no-install-suggests -y --force-yes \
    gcc ca-certificates \
    libxml2 libxslt1.1 \
    libcurl3 libcurl3-gnutls libcurl4-gnutls-dev libgnutls28-dev \
    python3.7 python3.7-dev python3-setuptools && \
    python3.7 setup.py install && \
    find . -name \*.pyc -delete && \
    python3.7 setup.py test
