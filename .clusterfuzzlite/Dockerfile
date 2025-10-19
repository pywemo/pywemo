FROM gcr.io/oss-fuzz-base/base-builder-python:v1@sha256:b76cddbc1e7e6c9fabce04da964ddada8d30d33b9687fd5c0f1b815fcffa06a7
RUN apt-get update && \
    apt-get install -y make autoconf automake libtool pip
COPY . $SRC/pywemo
WORKDIR pywemo
COPY .clusterfuzzlite/build.sh $SRC/
