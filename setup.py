from setuptools import setup, find_packages

setup(name='pywemo',
      version='0.3.1',
      description='Access WeMo switches using their SOAP API',
      url='http://github.com/balloob/pywemo',
      author='Paulus Schoutsen',
      author_email='Paulus@PaulusSchoutsen.nl',
      license='MIT',
      install_requires=['requests>=2.0'],
      packages=find_packages(),
      zip_safe=True)
