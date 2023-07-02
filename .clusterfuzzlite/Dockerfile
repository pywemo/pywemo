FROM gcr.io/oss-fuzz-base/base-builder-python:v1@sha256:65a7ddd08cb70765a19644c88bf5a26aa78ce1b1c1eeb23811137798abd4cf69
RUN apt-get update && \
    apt-get install -y make autoconf automake libtool pip
COPY . $SRC/pywemo
WORKDIR pywemo
COPY .clusterfuzzlite/build.sh $SRC/
