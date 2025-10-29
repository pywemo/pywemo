#!/bin/sh -eu

cd "$SRC/pywemo"
source "./scripts/common.sh"
enterVenv

# upgrade pip
pip install --upgrade pip

# install fuzzer dependencies
pip install \
  --require-hashes \
  --no-deps \
  --only-binary :all: \
  -r ./.clusterfuzzlite/requirements.txt

# install pyWeMo dependencies
poetryInstall

# use pyinstaller to build fuzzers
for fuzzer in $(find . -name '*_fuzz.py'); do
  fuzzer_basename=$(basename -s .py $fuzzer)
  fuzzer_package=${fuzzer_basename}.pkg

  pyinstaller --distpath $OUT --onefile --name $fuzzer_package $fuzzer

  echo "#!/bin/sh
# LLVMFuzzerTestOneInput for fuzzer detection.
this_dir=\$(dirname \"\$0\")
ASAN_OPTIONS=\$ASAN_OPTIONS:symbolize=1:external_symbolizer_path=\$this_dir/llvm-symbolizer:detect_leaks=0 \
\$this_dir/$fuzzer_package \$@" > $OUT/$fuzzer_basename
  chmod +x $OUT/$fuzzer_basename
done
