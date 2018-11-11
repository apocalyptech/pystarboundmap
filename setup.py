#!/usr/bin/env python
# vim: set expandtab tabstop=4 shiftwidth=4:

from setuptools import find_packages, setup
from pystarboundmap import __version__

def readme():
    with open('README.md') as f:
        return f.read()

setup(
    name='pystarboundmap',
    version=__version__,
    packages=find_packages(),
    include_package_data=True,
    license='BSD License',
    description='Starbound Map Viewer',
    long_description=readme(),
    long_description_content_type='text/markdown',
    url='https://github.com/apocalyptech/pystarboundmap',
    author='CJ Kucera',
    author_email='cj@apocalyptech.com',
    install_requires=[
        'Pillow ~= 5.3',
        'PyQt5 ~= 5.11',
        'appdirs ~= 1.4',
        'timeago ~= 1.0',
        'py-starbound',
        ],
    dependency_links=[
        'git+https://github.com/blixt/py-starbound.git#egg=py-starbound',
        ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: X11 Applications :: Qt',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Games/Entertainment',
        'Topic :: Utilities',
        ],
    entry_points={
        'gui_scripts': [
            'pystarboundmap = pystarboundmap.gui:main',
            ],
        },
)
