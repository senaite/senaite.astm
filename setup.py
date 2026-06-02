# -*- coding: utf-8 -*-

from setuptools import find_packages
from setuptools import setup


version = "2.0.0"


def _long_description():
    """README + CHANGES rendered as one markdown document on PyPI."""
    with open("README.md") as fh:
        readme = fh.read()
    with open("CHANGES.md") as fh:
        changes = fh.read()
    return readme + "\n\n" + changes


setup(
    name="senaite.astm",
    version=version,
    description="",
    long_description=_long_description(),
    long_description_content_type="text/markdown",
    license="GPLv2",
    # Get more strings from
    # http://pypi.python.org/pypi?:action=list_classifiers
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    keywords="",
    author="",
    author_email="",
    url="",
    packages=find_packages("src"),
    package_dir={"": "src"},
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        "hl7",
        "pydantic>=2",
        "requests",
    ],
    test_suite='senaite.astm.tests',
    # List additional groups of dependencies here (e.g. development
    # dependencies). You can install these using the following syntax,
    # for example:
    # $ pip install -e .[dev,test]
    extras_require={
        "dev": [
            "pytest",
            "coverage",
            "responses",
        ]
    },
    entry_points={
        "console_scripts": [
            "senaite-astm-server=senaite.astm.cli.astm_server:main",
            "senaite-astm-send=senaite.astm.sender:main",
            "senaite-astm-inspect=senaite.astm.inspect:main",
            "senaite-astm-simulator=senaite.astm.simulator:main",
            "senaite-hl7-server=senaite.astm.cli.hl7_server:main",
            "senaite-hl7-simulator=senaite.astm.cli.hl7_simulator:main",
        ]
    }
)
