from setuptools import setup, find_packages

setup(name='pywemo',
      version='0.3.15',
      description='Access WeMo switches using their SOAP API',
      url='http://github.com/pavoni/pywemo',
      author='Greg Dowling',
      author_email='mail@gregdowling.com',
      license='MIT',
      install_requires=['requests>=2.0'],
      packages=find_packages(),
      zip_safe=True)
