from setuptools import setup

setup(
    name="skydive-shell",
    version="0.3",
    entry_points={
        'console_scripts': [
            'skydive-shell=skydive_shell.shell:main',
        ],
    },
    install_requires=[
        'prompt-toolkit',
        'lark-parser',
        'pygments',
        'skydive-client>=0.4.5'
    ],
    packages=["skydive_shell"],
    test_suite="tests",
    author="Antoine Eiche",
    author_email="lewo@abesis.fr",
    description="An interactive Shell for Skydive",
    url="https://github.com/nlewo/skydive-shell",

)
