"""pyWeMo setup script."""

from setuptools import setup, find_packages

CONST_DESC = 'Lightweight Python module to discover and control WeMo devices'


setup(name='pywemo',
      version='0.4.40',
      description=CONST_DESC,
      long_description=open('README.rst').read(),
      url='http://github.com/pavoni/pywemo',
      author='Greg Dowling',
      author_email='mail@gregdowling.com',
      license='MIT',
      install_requires=['ifaddr>=0.1.0', 'requests>=2.0', 'six>=1.10.0'],
      packages=find_packages(),
      zip_safe=True,
      classifiers=[
          "Programming Language :: Python :: 2",
          "Programming Language :: Python :: 3",
          "License :: OSI Approved :: MIT License",
          "Operating System :: OS Independent",
          "Topic :: Home Automation"])
