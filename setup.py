from setuptools import setup, find_packages

from disco import VERSION

with open('requirements.txt') as f:
    requirements = f.readlines()
    f.close()

with open('README.md') as f:
    readme = f.read()
    f.close()

extras_require = {
    'voice': ['telecom-py==0.0.4'],
    'http': ['flask>=1.1.2'],
    'yaml': ['pyyaml>=5.3.1'],
    'music': ['yt-dlp>=2021.10.10'],
    'performance': [
        'earl-etf>=2.1.2',
        'regex>=2021.4.4',
        'ujson>=3.2.0',
        'wsaccel>=0.6.3',
    ],
    'sharding': ['gipc>=1.3.0'],
}

setup(
    name='betterdisco-py',
    author='The BetterDisco Team; b1nzy',
    url='https://github.com/elderlabs/betterdisco',
    version=VERSION,
    packages=find_packages(include=['disco*']),
    license='MIT',
    description='A Python library for Discord',
    long_description=readme,
    long_description_content_type="text/markdown",
    include_package_data=True,
    install_requires=requirements,
    extras_require=extras_require,
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: MIT License',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Topic :: Internet',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Utilities',
    ],
    python_requires='>=3.8',
)
