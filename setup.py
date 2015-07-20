from setuptools import setup

setup(name='pywemo',
      version='0.1',
      description='Access WeMo switches using their SOAP API',
      url='http://github.com/balloob/pywemo',
      author='Paulus Schoutsen',
      author_email='Paulus@PaulusSchoutsen.nl',
      license='MIT',
      install_requires=['requests>=2.0'],
      packages=['pywemo'],
      zip_safe=True)
