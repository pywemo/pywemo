FROM gcr.io/oss-fuzz-base/base-builder-python:v1@sha256:efe4ef7813ceb70c5e4d19b917bec8d39470c81790104390ba4d9139fe16a1a3
RUN apt-get update && \
    apt-get install -y make autoconf automake libtool pip
COPY . $SRC/pywemo
WORKDIR pywemo
COPY .clusterfuzzlite/build.sh $SRC/
