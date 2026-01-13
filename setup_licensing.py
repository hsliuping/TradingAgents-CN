from setuptools import setup, Extension
from Cython.Build import cythonize
import os

# 需要编译的文件
py_files = [
    'validator.py',
    'manager.py',
    'features.py',
]

extensions = []
for py_file in py_files:
    file_path = os.path.join('C:/TradingAgentsCN/release/TradingAgentsCN-portable/core/licensing', py_file)
    if os.path.exists(file_path):
        module_name = f'core.licensing.{py_file[:-3]}'
        extensions.append(Extension(
            module_name,
            [file_path],
            extra_compile_args=['/O2'] if os.name == 'nt' else ['-O3'],
        ))

setup(
    name='tradingagents-core-licensing',
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            'language_level': '3',
            'embedsignature': False,
            'boundscheck': False,
            'wraparound': False,
        },
        build_dir='build',
    ),
)
