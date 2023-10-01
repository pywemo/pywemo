FROM gcr.io/oss-fuzz-base/base-builder-python:v1@sha256:94b95a4ec2e75ef3df050d2e18a8005ee9d79d8a0e79790a51a8bb8ad72fe7f8
RUN apt-get update && \
    apt-get install -y make autoconf automake libtool pip
COPY . $SRC/pywemo
WORKDIR pywemo
COPY .clusterfuzzlite/build.sh $SRC/
