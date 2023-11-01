FROM gcr.io/oss-fuzz-base/base-builder-python:v1@sha256:10fb2d2f7fac49a7eac5d89c03aebb2ef33a69191a08bf052d88e5d230b7a34b
RUN apt-get update && \
    apt-get install -y make autoconf automake libtool pip
COPY . $SRC/pywemo
WORKDIR pywemo
COPY .clusterfuzzlite/build.sh $SRC/
