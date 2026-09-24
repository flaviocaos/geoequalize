# Empacotamento Windows — PyInstaller

Este guia explica como gerar um executável (`.exe`) standalone do
Satellite Image Corrector para distribuir em computadores Windows sem
precisar instalar Python.

## 1. Instalar o PyInstaller

Com o ambiente virtual ativado:

```bash
pip install pyinstaller
```

## 2. O desafio do GDAL/Rasterio

O maior obstáculo ao empacotar este app é que **GDAL/Rasterio dependem
de bibliotecas binárias nativas (DLLs) e arquivos de dados** (como
`gdal_data`, `proj_data`) que o PyInstaller não detecta automaticamente.
Sem isso, o `.exe` abre mas falha ao tentar abrir qualquer raster.

## 3. Comando básico (primeira tentativa)

```bash
pyinstaller --name SatelliteImageCorrector --windowed --onedir app/main.py
```

- `--windowed`: não abre um terminal por trás da janela Qt.
- `--onedir`: gera uma pasta com o `.exe` e as dependências (mais fácil
  de depurar que `--onefile`, que é mais lento para iniciar).

Esse comando provavelmente vai falhar silenciosamente em runtime ao
tentar ler arquivos raster — siga para o passo 4.

## 4. Arquivo `.spec` customizado (recomendado)

Gere primeiro o `.spec` padrão:

```bash
pyinstaller --name SatelliteImageCorrector --windowed --onedir app/main.py
```

Isso cria `SatelliteImageCorrector.spec` na raiz do projeto. Edite-o
para incluir os dados do GDAL/Rasterio e do PySide6/PyQtGraph:

```python
# SatelliteImageCorrector.spec
import rasterio
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

# Caminho de instalação do rasterio (contém os .dll/.pyd do GDAL embutido)
rasterio_path = Path(rasterio.__file__).parent

datas = []
binaries = []

# Coleta os dados de proj/gdal embutidos no pacote rasterio
datas += collect_data_files('rasterio')
binaries += collect_dynamic_libs('rasterio')

# PyQtGraph e matplotlib às vezes precisam de dados extras
datas += collect_data_files('pyqtgraph')

a = Analysis(
    ['app/main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        'rasterio.sample',
        'rasterio._io',
        'rasterio.crs',
        'rasterio.control',
        'rasterio.transform',
        'rasterio.vfs',
        'cv2',
        'skimage.exposure',
        'pyqtgraph',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SatelliteImageCorrector',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # janela sem terminal
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SatelliteImageCorrector',
)
```

Depois rode:

```bash
pyinstaller SatelliteImageCorrector.spec
```

O resultado fica em `dist/SatelliteImageCorrector/SatelliteImageCorrector.exe`.

## 5. Variáveis de ambiente do GDAL (se ainda houver erro)

Se ao abrir uma imagem o executável mostrar erro relacionado a
`PROJ` ou `GDAL_DATA`, pode ser necessário definir essas variáveis de
ambiente dentro do próprio `app/main.py`, **antes** de importar rasterio:

```python
import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # Executando como .exe empacotado pelo PyInstaller
    base_path = Path(sys._MEIPASS)
    os.environ["GDAL_DATA"] = str(base_path / "rasterio" / "gdal_data")
    os.environ["PROJ_LIB"] = str(base_path / "rasterio" / "proj_data")
```

Adicione esse bloco no topo de `app/main.py`, antes de qualquer outro
import. Os nomes exatos das subpastas (`gdal_data`, `proj_data`) podem
variar de acordo com a versão do rasterio instalada — confira o conteúdo
de `dist/SatelliteImageCorrector/` após o build para localizar onde o
PyInstaller efetivamente copiou esses arquivos.

## 6. Testando o executável

1. Copie a pasta `dist/SatelliteImageCorrector/` inteira para outro
   computador Windows (ou uma pasta limpa, fora do ambiente de
   desenvolvimento) para simular o uso real.
2. Execute `SatelliteImageCorrector.exe`.
3. Teste abrir um GeoTIFF real.
4. Teste exportar uma imagem corrigida.
5. Se algo falhar, rode temporariamente com `console=True` no `.spec`
   (e gere de novo) para ver mensagens de erro no terminal.

## 7. Problemas comuns

| Problema | Causa provável | Solução |
|---|---|---|
| `.exe` abre e fecha instantaneamente | Erro na inicialização, sem console para ver a mensagem | Gere uma versão com `console=True` para depurar |
| Erro `Unable to open EPSG support file gcs.csv` ou similar de PROJ | `PROJ_LIB`/`GDAL_DATA` não encontrados no pacote | Ver passo 5 |
| App abre, mas falha ao abrir qualquer imagem | DLLs do GDAL não foram copiadas | Confirme que `collect_dynamic_libs('rasterio')` está no `.spec` |
| Ícones do PySide6 ausentes / app com aparência quebrada | Plugins do Qt não copiados | Adicione `collect_data_files('PySide6')` aos `datas` do `.spec` |
| Antivírus bloqueia o `.exe` | Falso positivo comum em executáveis gerados por PyInstaller | Assinar digitalmente o executável (certificado), ou adicionar exceção no antivírus para testes internos |
| Build muito grande (300MB+) | Normal: GDAL + Qt + scikit-image são pesados | Use `--onedir` (não `--onefile`) e considere distribuir como instalador (Inno Setup) em vez de pasta solta |

## 8. Distribuição (opcional)

Para uma experiência de instalação mais profissional, considere usar o
[Inno Setup](https://jrsoftware.org/isinfo.php) para empacotar a pasta
`dist/SatelliteImageCorrector/` em um instalador `.exe` único, com
atalho no menu Iniciar e desinstalador — isso está fora do escopo deste
guia, mas é o passo natural seguinte para distribuição a usuários finais.