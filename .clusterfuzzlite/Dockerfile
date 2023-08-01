FROM gcr.io/oss-fuzz-base/base-builder-python:v1@sha256:660fc75af27e74f5893a502c40051853531edb5fadff815b4819d8392a9db291
RUN apt-get update && \
    apt-get install -y make autoconf automake libtool pip
COPY . $SRC/pywemo
WORKDIR pywemo
COPY .clusterfuzzlite/build.sh $SRC/
