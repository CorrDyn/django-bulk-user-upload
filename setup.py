from setuptools import find_packages, setup


def read(file_name):
    with open(file_name, 'r', encoding='utf-8') as r:
        return r.read()


setup(
    name='django-bulk-user-upload',
    version="0.1.0",
    url='https://github.com/CorrDyn/django-bulk-user-upload',
    license='MIT',
    description='Installable Django admin interface for bulk user creation from uploaded CSV file.',
    long_description=read('README.md'),
    long_description_content_type='text/markdown',
    author='JP Jorissen',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[req for req in read('requirements.txt').split('\n') if req],
    python_requires=">=3.6",
    zip_safe=False,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Internet :: WWW/HTTP',
    ],
)
