# Python para Análisis de Datos — Referencia Senior

App de referencia + notebooks ejecutables con todo lo que un analista de
datos senior debería saber de Python: librerías, análisis exploratorio,
estadística, visualización, machine learning y automatización — con
ejemplos orientados a finanzas/crédito y e-commerce/tech.

## Contenido

- **`app/index.html`** — app web autocontenida (sin build, sin dependencias)
  con los 8 módulos, código con syntax highlighting, búsqueda y modo
  claro/oscuro. Ábrela directamente en el navegador.
- **`notebooks/`** — un Jupyter Notebook ejecutable por módulo, con el mismo
  contenido en formato "corre y experimenta".
- **`data/`** — datasets sintéticos y reproducibles (crédito, ventas
  e-commerce/tech, precios de acciones) generados por
  `data/generate_datasets.py`.
- **`scripts/etl_credito.py`** — pipeline ETL real usado como ejemplo en el
  módulo de automatización (validación con `pandera`, tests en
  `scripts/test_etl_credito.py`).

## Módulos

| # | Módulo | Notebook |
|---|---|---|
| 01 | Fundamentos de Python para datos | `01_fundamentos_python_datos.ipynb` |
| 02 | Librerías clave: NumPy y Pandas avanzado | `02_librerias_numpy_pandas.ipynb` |
| 03 | SQL y bases de datos | `03_sql_bases_datos.ipynb` |
| 04 | Estadística aplicada | `04_estadistica_aplicada.ipynb` |
| 05 | Análisis Exploratorio de Datos (EDA) | `05_analisis_exploratorio_eda.ipynb` |
| 06 | Visualización de datos | `06_visualizacion_datos.ipynb` |
| 07 | Modelos predictivos y Machine Learning | `07_modelos_predictivos_ml.ipynb` |
| 08 | Automatización y producción | `08_automatizacion_pipelines.ipynb` |

## Uso

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Regenerar los datasets (opcional, ya están commiteados en data/)
python data/generate_datasets.py

# Abrir los notebooks
jupyter lab notebooks/

# Correr los tests del pipeline de automatización
pytest scripts/test_etl_credito.py -v
```

Para la app web, simplemente abre `app/index.html` en el navegador — no
requiere servidor.
