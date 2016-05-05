#!/usr/bin/env python3
import os
from setuptools import setup, find_packages


def get_readme():
    return open(os.path.join(os.path.dirname(__file__), 'README.rst')).read()

setup(
    author="Julio Gonzalez Altamirano",
    author_email='devjga@gmail.com',
    description="Converts tweet streams into an organized, story-telling web-page .",
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3 :: Only'
    ],
    install_requires=['pytz', 'python-dateutil', 'tweepy'],
    keywords="python twitter",
    license="MIT",
    long_description=get_readme(),
    name='conversationalist',
    packages=find_packages(include=['conversationalist', 'conversationalist.*'],
                           exclude=['tests', 'tests.*']),
    platforms=['Any'],
    url='https://github.com/jga/conversationalist',
    version='0.1.1',
)