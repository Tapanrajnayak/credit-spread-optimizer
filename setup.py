#!/usr/bin/env python3
"""
Setup script for credit-spread-optimizer.
"""

from setuptools import setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="credit-spread-optimizer",
    version="1.0.0",
    author="Tapan Nayak",
    author_email="nayaktapan37@yahoo.com",
    description="Institutional-grade credit spread screening and ranking system",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Tapanrajnayak/credit-spread-optimizer",
    packages=["cso"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Office/Business :: Financial :: Investment",
    ],
    python_requires=">=3.9",
    install_requires=[
        "numpy>=1.20.0",
        "pandas>=1.3.0",
    ],
    extras_require={
        "live": [
            "yfinance>=0.2.0",
        ],
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=3.0.0",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
