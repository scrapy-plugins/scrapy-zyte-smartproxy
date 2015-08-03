from setuptools import setup

setup(
    name='scrapy-crawlera',
    version='1.0.2',
    license='BSD',
    description='Crawlera middleware for Scrapy',
    author='Scrapinghub',
    author_email='opensource@scrapinghub.com',
    url='https://github.com/scrapinghub/scrapy-crawlera',
    py_modules=['crawlera', 'hubproxy'],
    platforms=['Any'],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
    ]
)
