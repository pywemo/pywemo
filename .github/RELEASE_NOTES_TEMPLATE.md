[![PyPI](https://img.shields.io/badge/pypi-${GITHUB_REF_NAME}-green.svg)](https://pypi.org/project/pywemo/${GITHUB_REF_NAME}/) [![Coverage Status](https://coveralls.io/repos/github/${GITHUB_REPOSITORY}/badge.svg?branch=${GITHUB_REF_NAME})](https://coveralls.io/github/${GITHUB_REPOSITORY}?branch=${GITHUB_REF_NAME}) [![SLSA](https://slsa.dev/images/gh-badge-level3.svg)](https://slsa.dev/)

${BODY}

**Release asset details**:

<details id="sha256"><summary><code>SHA256</code> checksums</summary>

```
${SHA256SUM}
```

</details>

<details id="sigstore"><summary>How to verify <code>sigstore</code> signatures</summary>
<a href="https://www.sigstore.dev/">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/sigstore/community/367eb1207779a8d92c80ffb05c5eb721bfd3b9ba/artwork/sigstore/horizontal/color%20reverse/sigstore_horizontal-colorreverse.svg">
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/sigstore/community/367eb1207779a8d92c80ffb05c5eb721bfd3b9ba/artwork/sigstore/horizontal/color/sigstore_horizontal-color.svg">
    <img alt="Sigstore" src="https://raw.githubusercontent.com/sigstore/community/367eb1207779a8d92c80ffb05c5eb721bfd3b9ba/artwork/sigstore/horizontal/color/sigstore_horizontal-color.svg" width="150">
  </picture>
</a>

Visit [sigstore.dev](https://www.sigstore.dev/) to learn more about sigstore signing and verification.

Certificate identity:

```
https://github.com/${GITHUB_WORKFLOW_REF}
```

Verify with [`sigstore-python`](https://github.com/sigstore/sigstore-python/):

```bash
# Download the release wheel and .sigstore file.
wget https://github.com/${GITHUB_REPOSITORY}/releases/download/${GITHUB_REF_NAME}/pywemo-${GITHUB_REF_NAME}-py3-none-any.whl
wget https://github.com/${GITHUB_REPOSITORY}/releases/download/${GITHUB_REF_NAME}/pywemo-${GITHUB_REF_NAME}-py3-none-any.whl.sigstore.json

# Install sigstore: https://github.com/sigstore/sigstore-python#installation
python -m pip install sigstore

# Verify that the wheel was built from this release.
python -m sigstore verify github \
    --bundle pywemo-${GITHUB_REF_NAME}-py3-none-any.whl.sigstore.json \
    --cert-identity https://github.com/${GITHUB_WORKFLOW_REF} \
    --sha ${GITHUB_SHA} \
    pywemo-${GITHUB_REF_NAME}-py3-none-any.whl
```

</details>

<details id="SLSA"><summary>How to verify <code>SLSA</code> provenance</summary>
<a href="https://slsa.dev/">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/slsa-framework/slsa/93cff4f95c07b095342ac256667594df038ad8d4/resources/assets/logo/horizontal/SVG/SLSA-logo-horizontal-white.svg">
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/slsa-framework/slsa/93cff4f95c07b095342ac256667594df038ad8d4/resources/assets/logo/horizontal/SVG/SLSA-logo-horizontal-original.svg">
    <img alt="SLSA" src="https://raw.githubusercontent.com/slsa-framework/slsa/93cff4f95c07b095342ac256667594df038ad8d4/resources/assets/logo/horizontal/SVG/SLSA-logo-horizontal-original.svg" width="150">
  </picture>
</a>

Visit [slsa.dev](https://slsa.dev/) to learn more about generating and verifying software provenance with SLSA.

SLSA verifier installation instructions can be found at [github.com/slsa-framework/slsa-verifier#installation](https://github.com/slsa-framework/slsa-verifier#installation).

```bash
# Download the release wheel and .intoto.jsonl file.
wget https://github.com/${GITHUB_REPOSITORY}/releases/download/${GITHUB_REF_NAME}/pywemo-${GITHUB_REF_NAME}-py3-none-any.whl
wget https://github.com/${GITHUB_REPOSITORY}/releases/download/${GITHUB_REF_NAME}/pywemo-${GITHUB_REF_NAME}.intoto.jsonl

# Verify that the wheel was built from this release.
slsa-verifier verify-artifact \
    --provenance-path pywemo-${GITHUB_REF_NAME}.intoto.jsonl \
    --source-uri github.com/${GITHUB_REPOSITORY} \
    --source-tag ${GITHUB_REF_NAME} \
    pywemo-${GITHUB_REF_NAME}-py3-none-any.whl
```

</details>
