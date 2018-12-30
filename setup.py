from setuptools import setup, find_packages

setup(name='pywemo',
<<<<<<< HEAD
      version='0.4.34',
      description='Lightweight Python module to discover and control WeMo devices',
=======
      version='0.4.33',
      description='Access WeMo switches using their SOAP API',
>>>>>>> parent of 328366e... Merge branch 'rediscovery' into master
      url='http://github.com/pavoni/pywemo',
      author='Greg Dowling',
      author_email='mail@gregdowling.com',
      license='MIT',
      install_requires=['netifaces>=0.10.0', 'requests>=2.0', 'six>=1.10.0'],
      packages=find_packages(),
      zip_safe=True)
