from setuptools import setup, find_packages

setup(name='pywemo',
      version='0.4.34',
      description='Lightweight Python module to discover and control WeMo devices',
      url='http://github.com/pavoni/pywemo',
      author='Greg Dowling',
      author_email='mail@gregdowling.com',
      license='MIT',
      install_requires=['netifaces>=0.10.0', 'requests>=2.0', 'six>=1.10.0'],
      packages=find_packages(),
      zip_safe=True)
