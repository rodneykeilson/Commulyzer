"""Setup minimal untuk instalasi editable proyek toxicity-facebook."""
from __future__ import annotations

from pathlib import Path

from setuptools import find_packages, setup

README = Path(__file__).with_name("README.md").read_text(encoding="utf-8")

setup(
    name="toxicity-facebook",
    version="0.1.0",
    description="Pipeline analisis toksisitas komunitas Facebook",
    long_description=README,
    long_description_content_type="text/markdown",
    author="Commulyzer Team",
    packages=find_packages(exclude=("tests", "docs")),
    python_requires=">=3.10",
    include_package_data=True,
)
