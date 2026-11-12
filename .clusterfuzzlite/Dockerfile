FROM gcr.io/oss-fuzz-base/base-builder-python:v1@sha256:21f6fab17ace4dc76e1c56de91ee95d3d03da021df94b41056ba036f6c6f55e9

RUN apt-get update && \
    apt-get install -y make autoconf automake libtool

COPY . $SRC/pywemo

WORKDIR pywemo

COPY .clusterfuzzlite/build.sh $SRC/
