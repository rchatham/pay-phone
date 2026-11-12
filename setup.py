#!/usr/bin/env python3
"""
Payphone System Library

A flexible framework for creating interactive phone systems with
physical payphone hardware or Arduino interfaces.
"""
from setuptools import setup, find_packages
import os

# Read README if it exists
long_description = "A flexible framework for creating interactive phone systems"
if os.path.exists("README.md"):
    with open("README.md", "r", encoding="utf-8") as fh:
        long_description = fh.read()

setup(
    name="payphone",
    version="0.1.0",
    author="Reid Chatham",
    description="A flexible framework for creating interactive phone systems",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    package_data={
        'payphone': ['audio_files/dtmf/*.wav'],
    },
    include_package_data=True,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
    python_requires=">=3.10",
    install_requires=[
        "pygame>=2.0.0",
        "python-dotenv>=0.19.0",
        "pyserial>=3.5",
    ],
    extras_require={
        "rpi": ["RPi.GPIO>=0.7.0"],  # Only needed for Raspberry Pi
        "recording": ["numpy>=1.19.0", "sounddevice>=0.4.6", "soundfile>=0.12.1"],
        "dev": ["pytest", "pytest-cov", "black", "flake8"],
    },
    entry_points={
        "console_scripts": [
            "payphone=payphone.main:main",
        ],
    },
)
