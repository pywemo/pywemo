from setuptools import setup, find_packages

setup(name='pywemo',
      version='0.4.22',
      description='Access WeMo switches using their SOAP API',
      url='http://github.com/pavoni/pywemo',
      author='Greg Dowling',
      author_email='mail@gregdowling.com',
      license='MIT',
      install_requires=['netifaces>=0.10.0', 'requests>=2.0', 'six>=1.10.0'],
      packages=find_packages(),
      zip_safe=True)
