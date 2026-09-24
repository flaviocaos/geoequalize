# Satellite Image Corrector

Aplicativo desktop para processamento visual e radiométrico de imagens
de satélite, drones e ortofotos. Suporta GeoTIFF, TIFF, JPEG, PNG e JP2.

## Status do projeto

✅ Todas as 9 fases planejadas foram implementadas.

## Funcionalidades

- **Visualização**: zoom, pan, ajuste à tela, leitura de metadados geoespaciais (CRS, transform, bounds, NoData, driver, compressão).
- **Histograma e contraste**: stretch linear/percentil/desvio padrão, normalização, equalização, CLAHE, gamma, brilho/contraste — com histograma antes/depois e estatísticas por banda.
- **Cor**: balanceamento Gray World/White Patch, ponto de referência (branco/cinza/preto), ajuste de canais RGB, temperatura, matiz/saturação, sombras/médios/realces, redução de dominância de cor, correção de vinheta e iluminação desigual, realces por classe (urbano/vegetação/solo/estradas).
- **Correções locais**: seleção retangular/poligonal, feather de borda, aplicação restrita à área selecionada, com histórico de desfazer/refazer.
- **Multibanda**: composição RGB customizável, presets de falsa-cor, estatísticas avançadas por banda (variância, contagem de NoData).
- **Exportação**: GeoTIFF/TIFF/PNG/JPEG preservando CRS/transform/NoData, processamento em blocos para arquivos grandes, relatório de processamento em TXT.
- **Projeto**: salvar/abrir projeto (JSON), histórico editável (ativar/desativar/remover/reordenar operações), presets prontos e personalizados, processamento em lote (batch).
- **Filtros avançados**: sharpening, unsharp mask, redução de ruído, redução de haze, controle de sombras/altas luzes, harmonização de ortomosaico, matching de histograma (entre imagens ou por região).

## Requisitos

- Python 3.10+
- Ver `requirements.txt`
- GDAL (recomenda-se conda-forge no Windows — ver nota em requirements.txt)

## Instalação

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

## Como executar

```bash
python -m app.main
```

## Como usar

1. **Abrir uma imagem**: menu *Arquivo → Abrir imagem...* e selecione um GeoTIFF, TIFF, JPEG, PNG ou JP2.
2. **Selecionar bandas**: no painel *Bandas* (direita), ajuste os índices R/G/B ou escolha um preset de composição (cor natural, falsa-cor, vegetação, etc.) e clique em *Aplicar composição*.
3. **Aplicar correções**:
   - Aba *Histograma*: escolha um método (stretch, CLAHE, gamma...), ajuste os parâmetros e clique em *Aplicar*.
   - Aba *Cor*: balanceamento de branco, canais, temperatura, saturação, redução de dominância de cor.
   - Aba *Avançado*: sharpening, redução de ruído, redução de haze, harmonização de ortomosaico.
4. **Aplicar correção local**: aba *Local* → escolha "Retangular" ou "Poligonal" → desenhe a seleção na imagem → ajuste o feather → escolha se usa o método configurado na aba Histograma ou Cor → clique em *Aplicar correção local*.
5. **Gerenciar histórico**: painel *Projeto* (esquerda) mostra todas as operações aplicadas; você pode desativar (checkbox), remover ou reordenar (▲▼) qualquer uma.
6. **Exportar GeoTIFF**: menu *Arquivo → Exportar...* → escolha formato, caminho e se quer só a composição RGB ou todas as bandas → acompanhe a barra de progresso.
7. **Salvar/abrir projeto**: painel *Projeto* → *Salvar projeto* (gera um `.json` com tudo) ou *Abrir projeto* para continuar depois.
8. **Presets**: escolha um preset pronto no combo do painel *Projeto* e clique em *Carregar preset*, ou salve sua própria combinação de correções com *Salvar como preset*.
9. **Processamento em lote**: painel *Projeto → Processar várias imagens...* → adicione arquivos, escolha pasta de saída → o pipeline atual é aplicado a todas.

## Limitações conhecidas

- As correções da aba "Avançado" (redução de haze, harmonização de ortomosaico, etc.) são heurísticas visuais, **não substituem correção atmosférica científica** calibrada radiometricamente.
- Os presets de composição de bandas (Fase 5) assumem ordens de banda genéricas; sempre confira/ajuste manualmente conforme o sensor real (Sentinel-2, Landsat, drone, etc.).
- A leitura de preview é sempre reduzida (configurável em `utils/config.py`, `preview_max_dim`); a exportação em resolução total relê o arquivo original diretamente, podendo ser mais lenta para arquivos muito grandes.
- O matching de histograma por região depende de duas seleções manuais sucessivas (referência → destino); não há detecção automática de blocos de ortomosaico.
- JP2 (JPEG2000) depende do suporte do GDAL instalado; alguns ambientes Windows podem precisar de drivers adicionais.

## Próximos passos (ideias de evolução futura)

- Suporte a mais formatos de exportação (COG — Cloud Optimized GeoTIFF).
- Detecção automática de faixas de voo em ortomosaicos para harmonização sem seleção manual.
- Correção atmosférica científica opcional (ex.: Dark Object Subtraction, 6S).
- Pré-visualização em GPU para acelerar CLAHE/filtros em imagens grandes.
- Suporte a anotações/vetores sobre a imagem (shapefile, GeoJSON).

## Estrutura do projeto

```
satellite_image_corrector/
├── app/
│   ├── main.py
│   └── ui/              # Todos os painéis e diálogos (PySide6)
├── core/                 # Lógica de processamento (sem dependência de Qt)
├── utils/                # Logging, configuração, validações
├── tests/                # Testes automatizados (pytest)
├── requirements.txt
├── pytest.ini
└── README.md
```

## Testes

```bash
pip install pytest
pytest
```

## Empacotamento Windows

Ver seção dedicada `EMPACOTAMENTO.md` (ou a seção equivalente neste documento gerada na Fase 9) para o passo a passo completo com PyInstaller.