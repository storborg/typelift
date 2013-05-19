from setuptools import setup


setup(name="typelift",
      version='0.1',
      description='What it sounds like',
      long_description='',
      classifiers=[
          'Programming Language :: Python :: 2.7',
      ],
      keywords='',
      url='http://github.com/storborg/typelift',
      author='Scott Torborg',
      author_email='storborg@gmail.com',
      install_requires=[
          'requests',
          'lxml',
      ],
      license='MIT',
      packages=['typelift'],
      entry_points=dict(console_scripts=[
          'typelift=typelift:main',
      ]),
      test_suite='nose.collector',
      tests_require=['nose'],
      zip_safe=False)
