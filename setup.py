import setuptools

with open('README.md', 'r', encoding='utf-8') as fh:
    long_description = fh.read()

setuptools.setup(
    name='ndspy-xzonn',
    version='4.3.0',
    author='RoadrunnerWMC',
    maintainer='Xzonn',
    maintainer_email='Xzonn@outlook.com',
    description='Independently maintained ndspy fork with additional Nintendo DS format support.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/Xzonn/ndspy',
    project_urls={
        'Issues': 'https://github.com/Xzonn/ndspy/issues',
        'Source': 'https://github.com/Xzonn/ndspy',
        'Upstream': 'https://github.com/RoadrunnerWMC/ndspy',
    },
    license='GPL-3.0-or-later',
    license_files=['LICENSE'],
    packages=setuptools.find_packages(),
    package_data={
        'ndspy': ['py.typed'],
    },
    python_requires='>=3.12',
    entry_points={
        'console_scripts': [
            'ndspy_codeCompression = ndspy.codeCompression:main',
            'ndspy_lz10 = ndspy.lz10:main',
            'ndspy_lz11 = ndspy.lz11:main',
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Programming Language :: Python :: 3.14',
        'Operating System :: OS Independent',
    ],
    extras_require={
        'test': ['pytest'],
    },
)
