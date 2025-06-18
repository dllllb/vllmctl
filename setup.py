from setuptools import setup, find_packages

setup(
    name="vllmctl",
    version="0.1.0",
    description="CLI tool for launching and managing vllm model servers via SSH and tmux",
    author="adefful46@gmail.com",
    license="MIT",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "typer>=0.9.0",
        "rich>=13.0.0",
        "psutil>=5.9.0",
        "requests>=2.28.0",
    ],
    entry_points={
        'console_scripts': [
            'vllmctl = vllmctl.cli:app',
        ],
    },
    python_requires=">=3.8,<4.0",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
) 