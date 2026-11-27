from setuptools import setup, find_packages

setup(
    name="ujit",
    version="1.0.0",
    description="Universal JIT: Pseudocode to bare-metal native machine code compiler for ClothOS and distributed runtimes",
    author="Antigravity Team & nasakib",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: C",
        "Topic :: Software Development :: Compilers",
    ],
    python_requires=">=3.8",
)
