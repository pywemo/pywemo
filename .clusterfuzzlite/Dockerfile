FROM gcr.io/oss-fuzz-base/base-builder-python:v1@sha256:a24766c85cedfe780727bd729d29ba1dd1f08803fad9085dbb945ef6b8880ddb
RUN apt-get update && \
    apt-get install -y make autoconf automake libtool pip
COPY . $SRC/pywemo
WORKDIR pywemo
COPY .clusterfuzzlite/build.sh $SRC/
