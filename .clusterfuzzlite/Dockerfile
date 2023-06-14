FROM gcr.io/oss-fuzz-base/base-builder-python:v1@sha256:f9c44973385710c6b34a917feedc38127ffe01d361515602b0ca515e55478ed4
RUN apt-get update && \
    apt-get install -y make autoconf automake libtool pip
COPY . $SRC/pywemo
WORKDIR pywemo
COPY .clusterfuzzlite/build.sh $SRC/
