import sys
from setuptools import setup, find_packages

from disco import VERSION

with open('requirements.txt') as f:
    requirements = f.readlines()

with open('README.md') as f:
    readme = f.read()

extras_require = {
    'voice': ['telecom-py==0.0.4'],
    'http': ['flask==1.1.2'],
    'yaml': ['pyyaml==5.3.1'],
    'music': ['youtube_dl>=2018.1.21'],
    'performance': [
        'earl-etf==2.1.2',
        'numpy==1.19.2',
        'ujson==3.2.0',
        'wsaccel==0.6.3',
    ],
    'sharding': ['gipc==1.1.0'],
    'docs': ['biblio==0.0.4'],
}

setup(
    name='disco-py',
    author='b1nzy',
    url='https://github.com/b1naryth1ef/disco',
    version=VERSION,
    packages=find_packages(include=['disco*']),
    license='MIT',
    description='A Python library for Discord',
    long_description=readme,
    long_description_content_type="text/markdown",
    include_package_data=True,
    install_requires=requirements,
    extras_require=extras_require,
    test_suite='tests',
    setup_requires=['pytest-runner==2.11.1'],
    tests_require=[
        'pytest==3.2.1',
        'pytest-benchmark==3.1.1',
        'flake8-tuple==0.2.13',
        'flake8-quotes==1.0.0',
        'flake8-comprehensions==1.4.1',
        'flake8-commas==2.0.0',
        'flake8-builtins==1.4.1',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: MIT License',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Topic :: Internet',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Utilities',
    ],
    python_requires='>=3.8',
)
