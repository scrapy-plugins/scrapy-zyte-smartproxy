from setuptools import setup

with open("README.rst", "rb") as f:
    readme = f.read().decode("utf-8")


setup(
    name="scrapy-zyte-smartproxy",
    version="2.4.1",
    license="BSD",
    description="Scrapy middleware for Zyte Smart Proxy Manager",
    long_description=readme,
    long_description_content_type="text/x-rst",
    maintainer="Raul Gallegos",
    maintainer_email="raul.ogh@gmail.com",
    author="Zyte",
    author_email="opensource@zyte.com",
    url="https://github.com/scrapy-plugins/scrapy-zyte-smartproxy",
    packages=["scrapy_zyte_smartproxy"],
    platforms=["Any"],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Framework :: Scrapy",
        "Intended Audience :: Developers",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: Proxy Servers",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    install_requires=["scrapy>=1.4.0", "six", "w3lib"],
)
