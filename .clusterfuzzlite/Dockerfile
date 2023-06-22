FROM gcr.io/oss-fuzz-base/base-builder-python:v1@sha256:57c0116b8e8468a830984889ed812f0c5bbbff7a468ecdc8da294d1250a3b5e7
RUN apt-get update && \
    apt-get install -y make autoconf automake libtool pip
COPY . $SRC/pywemo
WORKDIR pywemo
COPY .clusterfuzzlite/build.sh $SRC/
