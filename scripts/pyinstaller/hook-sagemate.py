"""PyInstaller hook for SageMate.

Ensures all dynamically imported modules and data files are collected.
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Collect all sagemate submodules (many are dynamically imported)
hiddenimports = collect_submodules("sagemate")

# Collect data files for key packages
datas = []
datas += collect_data_files("jieba", include_py_files=False)
datas += collect_data_files("jinja2", include_py_files=False)
datas += collect_data_files("fastapi", include_py_files=False)
