# -*- mode: python ; coding: utf-8 -*-
# GeoEqualize.spec — arquivo de empacotamento PyInstaller
# Gerado para o GeoEqualize v1.0 (Fases 0-17)

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

block_cipher = None

# ----------------------------------------------------------------------
# Coleta de dados e binários das dependências problemáticas
# ----------------------------------------------------------------------
datas = []
binaries = []

# PySide6 — coleta explícita de todos os dados e submódulos
datas += collect_data_files('PySide6')
binaries += collect_dynamic_libs('PySide6')

# Rasterio (traz GDAL embutido — DLLs + dados de projeção)
datas += collect_data_files('rasterio')
binaries += collect_dynamic_libs('rasterio')

# Pyqtgraph
datas += collect_data_files('pyqtgraph')

# Matplotlib (fontes, estilos, etc.)
datas += collect_data_files('matplotlib')

# Scikit-learn (modelos, dados internos)
datas += collect_data_files('sklearn')

# Scipy
datas += collect_data_files('scipy')

# Reportlab (fontes embutidas)
datas += collect_data_files('reportlab')

# Skimage (scikit-image)
datas += collect_data_files('skimage')

# Assets do projeto (logo SVG)
datas += [('assets', 'assets')]

# Forçar inclusão de arquivos específicos do rasterio que o PyInstaller perde
import site
site_packages = site.getsitepackages()
rasterio_path = None
for sp in site_packages:
    candidate = Path(sp) / 'rasterio'
    if candidate.exists():
        rasterio_path = candidate
        break

if rasterio_path is None:
    # tenta via venv
    rasterio_path = Path('venv/Lib/site-packages/rasterio')

if rasterio_path.exists():
    # inclui todos os .py e .pyd do rasterio explicitamente
    for f in rasterio_path.glob('*.py'):
        datas.append((str(f), 'rasterio'))
    for f in rasterio_path.glob('*.pyd'):
        binaries.append((str(f), 'rasterio'))

# ----------------------------------------------------------------------
# Hidden imports: módulos que o PyInstaller não detecta automaticamente
# ----------------------------------------------------------------------
hidden_imports = [
    # PySide6 — todos os módulos usados no projeto
    'PySide6',
    'PySide6.QtWidgets',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtSvg',
    'PySide6.QtSvgWidgets',
    'PySide6.QtOpenGL',
    'PySide6.QtPrintSupport',
    'shiboken6',
    'rasterio.sample',
    'rasterio._io',
    'rasterio.crs',
    'rasterio.control',
    'rasterio.transform',
    'rasterio.vfs',
    'rasterio.enums',
    'rasterio.windows',

    # PySide6
    'PySide6.QtSvg',
    'PySide6.QtSvgWidgets',
    'shiboken6',

    # Scikit-learn
    'sklearn.utils._typedefs',
    'sklearn.utils._heap',
    'sklearn.utils._sorting',
    'sklearn.utils._vector_sentinel',
    'sklearn.neighbors._partition_nodes',
    'sklearn.cluster._k_means_common',
    'sklearn.cluster._k_means_lloyd',
    'sklearn.cluster._k_means_elkan',
    'sklearn.cluster._k_means_minibatch',

    # Scipy
    'scipy.ndimage',
    'scipy.ndimage._ni_support',
    'scipy.special._ufuncs',
    'scipy._lib.messagestream',

    # Matplotlib
    'matplotlib.backends.backend_agg',

    # Pyqtgraph
    'pyqtgraph.graphicsItems.PlotItem',
    'pyqtgraph.graphicsItems.PlotDataItem',
    'pyqtgraph.graphicsItems.PlotCurveItem',

    # Skimage
    'skimage.exposure',
    'skimage.filters',

    # OpenCV
    'cv2',

    # Outros
    'numpy',
    'PIL',
    'reportlab.graphics',
    'reportlab.platypus',
    'reportlab.lib',
]

# Adiciona todos os submódulos do PySide6, rasterio, sklearn e scipy
hidden_imports += collect_submodules('PySide6')
hidden_imports += collect_submodules('rasterio')
hidden_imports += collect_submodules('sklearn')
hidden_imports += collect_submodules('scipy.ndimage')

# ----------------------------------------------------------------------
# Análise principal
# ----------------------------------------------------------------------
a = Analysis(
    ['app/main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'PyQt5',
        'PyQt6',
        'IPython',
        'jupyter',
        'notebook',
        'torch',
        'tensorflow',
        'rasterio.serde',  # não existe no rasterio 1.5.0
    ],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GeoEqualize',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,       # sem janela de terminal
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,           # adicione um .ico aqui se quiser ícone no .exe
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GeoEqualize',
)