from setuptools import setup, find_packages

setup(
    name="aiogh",
    version="0.0.1dev",
    packages=find_packages(),
    install_requires=["aiohttp<0.18.0"],
)
