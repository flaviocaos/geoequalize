# 🛰️ GeoEqualize

**Aplicativo desktop para processamento visual, radiométrico e geoespacial de imagens de satélite, drones e ortofotos.**

Suporta GeoTIFF, TIFF, JPEG, PNG e JP2, preservando o georreferenciamento (CRS, transform, NoData) do início ao fim.

![Versão](https://img.shields.io/badge/versão-1.0.0-blue)
![Plataforma](https://img.shields.io/badge/plataforma-Windows%2010%20%7C%2011-lightgrey)
![Python](https://img.shields.io/badge/python-3.10%2B-yellow)
![Interface](https://img.shields.io/badge/interface-PySide6-green)

---

## 📥 Download

A forma mais simples de usar o GeoEqualize é baixar o executável pronto, sem precisar instalar Python nem dependências.

👉 **[Baixar a versão mais recente](https://github.com/flaviocaos/geoequalize/releases/latest)**

1. Baixe o arquivo `GeoEqualize-v1.0-Windows.zip`
2. Clique com o botão direito no arquivo → **Extrair Tudo...** e escolha uma pasta
3. Abra a pasta extraída e clique duas vezes em `GeoEqualize.exe`

> ⚠️ **Importante:** não execute o `GeoEqualize.exe` direto de dentro do `.zip`. Extraia a pasta inteira primeiro; o executável depende dos arquivos da pasta `_internal`.

> ℹ️ **Aviso do Windows:** na primeira execução, o Windows SmartScreen pode exibir "O Windows protegeu o computador", porque o executável ainda não possui assinatura digital. Clique em **Mais informações → Executar assim mesmo**.

---

## ✨ Funcionalidades

### 🖼️ Visualização e metadados
- Zoom, pan e ajuste à tela
- Leitura de metadados geoespaciais: CRS, transform, bounds, NoData, driver e compressão
- Perfil espectral de pixels

### 📊 Histograma e contraste
- Stretch linear, por percentil e por desvio padrão
- Normalização, equalização, CLAHE, gamma, brilho e contraste
- Histograma antes/depois e estatísticas por banda

### 🎨 Cor
- Balanceamento Gray World e White Patch
- Ponto de referência (branco, cinza ou preto)
- Ajuste de canais RGB, temperatura, matiz e saturação
- Sombras, médios e realces
- Redução de dominância de cor
- Correção de vinheta e de iluminação desigual
- Realces por classe (urbano, vegetação, solo, estradas)

### ✂️ Correções locais
- Seleção retangular ou poligonal com feather de borda
- Aplicação restrita à área selecionada
- Desfazer/refazer

### 🌈 Multibanda
- Composição RGB customizável
- Presets de falsa-cor
- Estatísticas avançadas por banda (variância, contagem de NoData)

### 🛰️ Sensoriamento Remoto
- Índices espectrais: NDVI, NDWI, SAVI e EVI
- Band math (álgebra de bandas)
- Correção atmosférica por Dark Object Subtraction (DOS)

### 🗺️ Geoprocessamento
- Reclassificação
- Análise multicritério (MCDA)
- Modelagem de mudanças com CA-Markov
- Classificação não supervisionada com K-Means

### 🔧 Filtros avançados
- Sharpening e unsharp mask
- Redução de ruído e de haze
- Controle de sombras e altas luzes
- Harmonização de ortomosaico
- Matching de histograma (entre imagens ou por região)

### 🤖 Agente local de IA
- Assistente de IA integrado ao aplicativo, executado localmente

### 📄 Relatórios e exportação
- Exportação em GeoTIFF, TIFF, PNG e JPEG preservando CRS, transform e NoData
- Processamento em blocos para arquivos grandes
- Relatórios em PDF bilíngues (português/inglês)
- Relatório de processamento em TXT

### 💾 Projetos e produtividade
- Salvar e abrir projetos (JSON)
- Histórico editável: ativar, desativar, remover e reordenar operações
- Presets prontos e personalizados
- Processamento em lote (batch)

---

## 🚀 Como usar

1. **Abrir uma imagem:** menu **Arquivo → Abrir imagem...** e selecione um GeoTIFF, TIFF, JPEG, PNG ou JP2.
2. **Selecionar bandas:** no painel **Bandas**, ajuste os índices R/G/B ou escolha um preset de composição (cor natural, falsa-cor, vegetação etc.) e clique em **Aplicar composição**.
3. **Aplicar correções:**
   - **Histograma:** escolha um método (stretch, CLAHE, gamma...), ajuste os parâmetros e clique em **Aplicar**.
   - **Cor:** balanceamento de branco, canais, temperatura, saturação, redução de dominância de cor.
   - **Avançado:** sharpening, redução de ruído, redução de haze, harmonização de ortomosaico.
4. **Correção local:** aba **Local** → escolha **Retangular** ou **Poligonal** → desenhe a seleção → ajuste o feather → clique em **Aplicar correção local**.
5. **Gerenciar histórico:** o painel **Projeto** mostra todas as operações aplicadas; é possível desativar, remover ou reordenar (▲▼) cada uma.
6. **Exportar:** menu **Arquivo → Exportar...** → escolha formato, caminho e se deseja apenas a composição RGB ou todas as bandas.
7. **Projetos e presets:** no painel **Projeto**, salve ou abra projetos `.json`, carregue presets prontos ou salve os seus.
8. **Processamento em lote:** painel **Projeto → Processar várias imagens...** → adicione os arquivos e escolha a pasta de saída; o pipeline atual é aplicado a todas.

---

## 🧑‍💻 Executar a partir do código-fonte

### Requisitos
- Python 3.10 ou superior
- Dependências listadas em `requirements.txt`
- GDAL (no Windows, recomenda-se instalar via conda-forge; veja a nota em `requirements.txt`)

### Instalação

```powershell
git clone https://github.com/flaviocaos/geoequalize.git
cd geoequalize
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Executar

```powershell
python -m app.main
```

### Testes

```powershell
pip install pytest
pytest
```

### Gerar o executável (Windows)

O empacotamento é feito com PyInstaller a partir do arquivo `GeoEqualize.spec`:

```powershell
pip install pyinstaller
pyinstaller GeoEqualize.spec --noconfirm
```

O resultado fica em `dist\GeoEqualize\`. Para o passo a passo completo, veja [`EMPACOTAMENTO.md`](EMPACOTAMENTO.md).

> 💡 Instale o PyInstaller **dentro do venv** do projeto. Se o venv for criado em outra pasta e o projeto for movido, recrie o venv no novo caminho, pois ele guarda caminhos absolutos.

---

## 📁 Estrutura do projeto

```
geoequalize/
├── app/
│   ├── main.py              # Ponto de entrada
│   └── ui/                  # Interface (PySide6): janela principal, painéis e diálogos
├── core/                    # Lógica de processamento (sem dependência de Qt)
├── utils/                   # Logging, configuração e validações
├── assets/                  # Recursos visuais
├── tests/                   # Testes automatizados (pytest)
├── GeoEqualize.spec         # Configuração do PyInstaller
├── EMPACOTAMENTO.md         # Guia de empacotamento para Windows
├── requirements.txt
├── pytest.ini
└── README.md
```

As pastas `build/`, `dist/`, `logs/` e `venv/` são geradas localmente e não devem ser versionadas.

---

## ⚠️ Limitações conhecidas

- As correções da aba **Avançado** (redução de haze, harmonização de ortomosaico etc.) são heurísticas visuais e não substituem uma correção atmosférica com calibração radiométrica completa.
- Os presets de composição de bandas assumem ordens de banda genéricas; confira e ajuste conforme o sensor real (Sentinel-2, Landsat, drone etc.).
- A pré-visualização é feita em resolução reduzida (configurável em `utils/config.py`, `preview_max_dim`); a exportação em resolução total relê o arquivo original e pode ser mais lenta em arquivos muito grandes.
- O matching de histograma por região depende de duas seleções manuais sucessivas (referência → destino).
- O suporte a JP2 (JPEG2000) depende dos drivers do GDAL instalado.
- O executável ainda não possui assinatura digital (ver aviso do SmartScreen acima).

---

## 🗺️ Roadmap

- [ ] **Detecção de objetos com YOLOv8** (edificações, pivôs, veículos e outros alvos em imagens aéreas)
- [ ] Ícone próprio no executável
- [ ] Instalador para Windows (atalhos no menu Iniciar, sem necessidade de extrair zip)
- [ ] Assinatura digital do executável
- [ ] Exportação em COG (Cloud Optimized GeoTIFF)
- [ ] Detecção automática de faixas de voo para harmonização de ortomosaicos
- [ ] Correção atmosférica avançada (ex.: 6S)
- [ ] Pré-visualização acelerada por GPU para filtros em imagens grandes
- [ ] Suporte a vetores sobre a imagem (Shapefile, GeoJSON)

---

## 👤 Autor

Desenvolvido por **Flavio Silva** — **FS Geotecnologias**

Sugestões, bugs e ideias: abra uma [Issue](https://github.com/flaviocaos/geoequalize/issues).
