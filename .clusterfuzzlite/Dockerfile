FROM gcr.io/oss-fuzz-base/base-builder-python:v1

COPY . $SRC/pywemo

WORKDIR pywemo

COPY .clusterfuzzlite/build.sh $SRC/
