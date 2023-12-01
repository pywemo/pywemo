FROM gcr.io/oss-fuzz-base/base-builder-python:v1@sha256:9fe9ad3db3d1f2935a4da5308b6e5c7e044368a5e076dfe72b7fa61740e90491
RUN apt-get update && \
    apt-get install -y make autoconf automake libtool pip
COPY . $SRC/pywemo
WORKDIR pywemo
COPY .clusterfuzzlite/build.sh $SRC/
