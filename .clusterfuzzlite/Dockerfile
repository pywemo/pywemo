FROM gcr.io/oss-fuzz-base/base-builder-python:v1@sha256:6a47ed07cd7215f5a7894dd62dd2f5fb4c0e7bf9e6d546cb407ee97d25147dac
RUN apt-get update && \
    apt-get install -y make autoconf automake libtool pip
COPY . $SRC/pywemo
WORKDIR pywemo
COPY .clusterfuzzlite/build.sh $SRC/
