from setuptools import setup

setup(
    name='scrapy-crawlera',
    version='1.0.0',
    license='BSD',
    description='Crawlera middleware for Scrapy',
    author='Scrapinghub',
    author_email='info@scrapinghub.com',
    url='https://github.com/scrapinghub/scrapy-crawlera',
    packages=['crawlera'],
    platforms=['Any'],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
    ],
    install_requires=['Scrapy>=0.22.0']
)
