from setuptools import setup, find_packages

setup(
    name="Tapri",
    version="1.0.0",
    author="Soumyajit Deb",
    author_email="debsoumyajit100@gmail.com",
    description="Async chat server with ordered message delivery",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/hyp3r5pace/tapri",

    # automatically find packages
    packages=find_packages(),

    # no runtime dependencies (only uses standard library)
    install_requires = [],

    # Development dependencies
    extra_requires = {
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.1.0",
        ],
    },

    # Python version requirement
    python_requires=">=3.9",

    # Create command-line tools
    entry_points={
        "console_scripts": [
            "tapri-server=server.server:main",
            "tapri-client=client.client:main",
        ],
    },

    # Project classification
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Communications :: Chat",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)