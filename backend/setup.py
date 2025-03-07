from setuptools import setup, find_packages

setup(
    name="politik",
    version="0.1",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "fastapi",
        "uvicorn",
        "python-dotenv",
        "requests",
        "websockets"
    ],
) 