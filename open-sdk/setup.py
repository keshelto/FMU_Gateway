from pathlib import Path

from setuptools import find_packages, setup

setup(
    name="fmu-gateway-sdk",
    version="0.1.0",
    description="Python SDK for the FMU Gateway service",
    author="FMU Gateway",
    packages=find_packages(),
    install_requires=["requests>=2.28"],
    long_description=Path("README.md").read_text(),
    long_description_content_type="text/markdown",
)
