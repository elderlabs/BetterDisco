from setuptools import setup, find_packages

from disco import VERSION

with open('requirements.txt') as f:
    requirements = f.readlines()
    f.close()

with open('README.md') as f:
    readme = f.read()
    f.close()

extras_require = {
    'voice': ['pynacl>=1.5.0', 'libnacl>=2.1.0'],
    'http': ['flask>=2.1.1'],
    'yaml': ['pyyaml>=5.3.1'],
    'music': ['yt-dlp>=2022.3.8.2'],
    'performance': [
        'erlpack>=1.0.0',
        'regex>=2022.3.15',
        'pylibyaml>=0.1.0',
        'ujson>=5.2.0',
        'wsaccel>=0.6.3',
    ],
    'sharding': ['gipc>=1.6.0', 'dill>=0.3.6'],
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
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Topic :: Internet',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Utilities',
    ],
    python_requires='>=3.8',
)
