FROM gcr.io/oss-fuzz-base/base-builder-python:v1@sha256:c534d211cc36cc71d8a9d82827aeca4889eb7c422f3568fabaea58f34d004ebc
RUN apt-get update && \
    apt-get install -y make autoconf automake libtool pip
COPY . $SRC/pywemo
WORKDIR pywemo
COPY .clusterfuzzlite/build.sh $SRC/
