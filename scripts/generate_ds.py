#!/usr/bin/env python
"""Script to generate .py files from .xsd using generateDS.

generateDS is used to auto-generate the necessary python modules to support
the UPnP device and service specifications. The purpose of this script is
mainly to document the local changes made after running generateDS. Putting
the local changes in this script makes the builds repeatable and hopefully
allows for easier upgrading to future versions of generateDS.
"""
from __future__ import annotations

import concurrent.futures
import os
import subprocess
import sys
import sysconfig
import tempfile


def generate_module(xsd_path: str) -> None:
    """Run generateDS and apply pyWeMo specific modifications."""
    module = run_generate_ds(xsd_path)

    # Modifications for pyWeMo.
    module = remove_python_version(module)
    module = remove_six_import(module)
    module = disable_code_analyzers(module)
    module = format_with_black(module)

    # Read the existing module
    existing_path = xsd_path.replace(".xsd", ".py")
    with open(existing_path, encoding="utf-8") as in_file:
        existing = in_file.read()
    if existing != module:
        # Write the Python module.
        with open(existing_path, "w", encoding="utf-8") as out_file:
            out_file.write(module)
        print(f"Wrote {existing_path}")


def run_generate_ds(xsd_path: str) -> str:
    """Run generateDS and return the generated module a string."""
    with tempfile.TemporaryDirectory() as path:
        py_name = os.path.basename(xsd_path).replace(".xsd", ".py")
        py_path = os.path.join(path, py_name)
        scripts_dir = sysconfig.get_path("scripts")
        subprocess.run(
            [
                sys.executable,
                os.path.join(scripts_dir, "generateDS.py"),
                "-f",
                "--no-dates",
                "-o",
                py_path,
                xsd_path,
            ],
            check=True,
        )
        with open(py_path, "r", encoding="utf-8") as py_file:
            output = py_file.read()
    # Remove paths related to running generateDS.py.
    output = output.replace(os.path.join(scripts_dir, ""), "")
    output = output.replace(repr(os.path.join(path, py_name)), repr(py_name))
    output = output.replace(os.path.join(path, ""), "")
    return output


def remove_python_version(module: str) -> str:
    """Remove the Python version from the module header comments.

    generateDS includes a Python version string at the top of the file header.
    This version string will be different for each version of Python and means
    the file can not be reproduced exactly on different platforms. This helper
    removes the Python version string.
    """
    return module.replace(sys.version.replace("\n", " "), "[sys.version]", 1)


def remove_six_import(module: str) -> str:
    """Replace the six import with its Python 3 equivalent.

    generateDS aims to maintain Python 2 & Python 3 compatibility for the
    generated files. It does so using the six library. pyWeMo only depends on
    Python 3, so six is not needed. six would need to be added as a dependency
    of pyWeMo if it was not removed here.
    """
    return module.replace(
        "from six.moves import zip_longest",
        "from itertools import zip_longest",
        1,
    )


def disable_code_analyzers(module: str) -> str:
    """Add comments to the file to disable code analyzers.

    The generateDS output isn't meant to be viewed or edited by a human. It
    also doesn't pass in many linting/code-auditing tools. Add comments to the
    generated file to disable code analyzers.
    """
    disabling_lines = [
        "# flake8: noqa",
        "# isort: skip_file",
        "# mypy: ignore-errors",
        "# pylint: skip-file",
    ]
    # Add these comments on the first empty line in the file.
    return module.replace(
        "\n" * 2,
        "\n" + "\n".join(disabling_lines) + "\n" * 2,
        1,
    )


def format_with_black(module: str) -> str:
    """Format the module using black.

    This is done as a way to avoid small changes due to whitespace or
    formatting between versions of generateDS.
    """
    process = subprocess.run(
        ["black", "-"],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
        input=module,
    )
    return process.stdout


def main(args: list[str]) -> None:
    """Generate python modules for xsd input files."""
    if not (xsd_files := args[1:]):
        sys.stderr.write(f"Usage: {args[0]} <xsd_file> [<xsd_file> ...]")
        sys.stderr.write(os.linesep * 2)
        sys.exit(1)

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=len(xsd_files)
    ) as pool:
        futures = [pool.submit(generate_module, file) for file in xsd_files]
    for future in futures:
        future.result()  # Raises any exceptions that happened in the thread.


if __name__ == "__main__":
    main(sys.argv)
