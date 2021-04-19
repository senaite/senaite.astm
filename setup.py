# -*- coding: utf-8 -*-

from setuptools import find_packages
from setuptools import setup


version = "1.0.0"

setup(
    name="senaite.astm",
    version=version,
    description="",
    long_description=open("README.md").read(),
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
    namespace_packages=["senaite"],
    include_package_data=True,
    zip_safe=False,
    install_requires=[
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
        ]
    },
    entry_points={
        "console_scripts": [
            "senaite-astm-server=senaite.astm.server:main",
            "senaite-astm-send=senaite.astm.sender:main",
        ]
    }
)
