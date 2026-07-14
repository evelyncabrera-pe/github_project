# 💬 Voz del Cliente en Banca Digital — Análisis de Sentimiento y Grafo de Palabras

Pipeline de analytics end-to-end que convierte comentarios de clientes en canales
digitales (app móvil, banca en línea, chat/call center) en **insights accionables
de negocio**, con un dashboard interactivo para explorarlos.

Proyecto de portafolio enfocado en el rol de **data analytics translator**: no solo
"corre un modelo de NLP", sino que traduce su salida a categorías, métricas y
recomendaciones que un equipo de CX, producto o riesgo pueda usar para priorizar.

> ⚠️ El dataset por defecto es **sintético** (generado con `scripts/generate_sample_data.py`)
> para que el proyecto se pueda clonar y correr sin depender de internet ni de datos
> reales de terceros. El pipeline también soporta datos reales (ver "Fuentes de datos").

## El problema de negocio

Los canales digitales de banca (apps, banca en línea, chat) generan miles de
comentarios y calificaciones de clientes que rara vez se leen de forma sistemática.
El resultado: los equipos de producto y CX no saben, con evidencia, **cuáles son
los 3-4 temas que más friccionan la experiencia del cliente esta semana**, ni si
esa fricción está mejorando o empeorando en el tiempo.

Este proyecto responde tres preguntas que un stakeholder de negocio haría:

1. ¿Qué tan positiva o negativa es la percepción del cliente, y cómo cambia en el tiempo?
2. ¿Sobre qué temas se quejan o elogian más (tecnología, atención, costos, seguridad, tiempos)?
3. ¿Qué palabras concretas —evidencia textual— sustentan esos temas, para poder
   citarlas en una conversación con negocio?

## Demo

```
python scripts/run_pipeline.py      # genera data/processed/*
streamlit run app/dashboard.py      # abre el dashboard interactivo
```

## Arquitectura del pipeline

```
┌──────────────┐   ┌───────────────┐   ┌───────────────┐   ┌───────────────┐   ┌──────────────┐
│  Ingestión   │ → │   Limpieza    │ → │  Sentimiento  │ → │ Temas negocio │ → │ Grafo palabras│
│ (conectores) │   │ (normalización)│   │  (léxico ES)  │   │  + cat. NPS   │   │  (NetworkX)   │
└──────────────┘   └───────────────┘   └───────────────┘   └───────────────┘   └──────────────┘
                                                                                        │
                                                                                        ▼
                                                                          data/processed/*.csv, *.html
                                                                                        │
                                                                                        ▼
                                                                       Dashboard Streamlit (solo lectura)
```

Decisión de diseño clave: **el pipeline corre offline (batch)** y guarda los
resultados en `data/processed/`. El dashboard **nunca** vuelve a calcular
sentimiento ni hace scraping en cada refresco — solo lee esos artefactos. Esto lo
hace rápido y liviano de desplegar (p. ej. en Streamlit Community Cloud) sin
necesidad de cargar ningún modelo pesado en el servidor del dashboard.

## Fuentes de datos ("busca la mejor forma")

El proyecto usa una capa de **conectores intercambiables** (`src/customer_insights/ingestion/`)
para que la fuente de datos no esté acoplada al resto del pipeline:

| Conector | Qué hace | Cuándo usarlo |
|---|---|---|
| `CSVConnector` + dataset de muestra | Lee `data/sample/resenas_banca_muestra.csv`, 320 comentarios sintéticos realistas de banca digital en español | Por defecto — no requiere internet, garantiza que el repo funcione siempre |
| `CSVConnector` + dataset propio | Lee cualquier CSV (encuesta NPS, export de CRM, dataset público de Kaggle) mapeando sus columnas al esquema estándar | Cuando tengas datos reales de encuestas/NPS |
| `PlayStoreConnector` | Extrae en vivo reseñas reales y públicas de apps de banca móvil (Google Play Store) vía `google-play-scraper` | Para una demo con datos 100% reales y actuales; ver `config/settings.yaml` para configurar los `app_id` |

Se evaluó usar datasets públicos ya empaquetados (Kaggle) para reseñas bancarias en
español, pero no se encontró ninguno robusto, vigente y en español enfocado en banca
digital — la mayoría son en inglés o de otros verticales. Por eso el pipeline
prioriza: (1) un conector real y reproducible (Play Store, con `lang=es`) y (2) un
dataset sintético versionado como fallback confiable para que cualquiera pueda
correr el proyecto sin fricción. Correr con datos reales es un cambio de un flag:

```
python scripts/run_pipeline.py --fuente play_store
python scripts/run_pipeline.py --fuente csv --csv-path data/raw/mi_dataset.csv
```

## Metodología de sentimiento

Backend por defecto: **motor léxico en español** (`processing/lexicon_es.py` +
`processing/sentiment.py`), con manejo de negaciones ("no resolvió" invierte la
polaridad de "resolvió") e intensificadores ("muy lento" pesa más que "lento").

Se eligió deliberadamente sobre un modelo transformer como backend por defecto por
dos razones de negocio, no solo técnicas:

- **Explicabilidad**: cada clasificación se puede justificar palabra por palabra
  frente a un stakeholder no técnico ("se marcó negativo por: *pésimo*, *grosero*").
- **Costo de despliegue**: no requiere descargar ni servir un modelo BERT (~500 MB+),
  lo que mantiene el dashboard ligero y desplegable en un tier gratuito.

Para mayor precisión hay un backend opcional basado en
[pysentimiento](https://github.com/pysentimiento/pysentimiento) (RoBERTuito, BERT
en español), pensado para correr en el paso batch del pipeline, no en el dashboard:

```
pip install -r requirements-optional.txt
python scripts/run_pipeline.py --backend-sentimiento transformer
```

## Grafo de palabras

Se construye un grafo de co-ocurrencia (`graph/word_graph.py`, NetworkX) por
separado para comentarios positivos y negativos: los nodos son palabras, el tamaño
del nodo es su frecuencia, y una arista conecta dos palabras que aparecen juntas en
el mismo comentario (el grosor es cuántas veces). Se calculan métricas de
centralidad (grado, intermediación) para identificar qué palabras actúan como
"puente" entre temas — típicamente los focos de dolor o de fortaleza más
transversales. Se visualiza de forma interactiva con `pyvis`.

## El dashboard

`app/dashboard.py` (Streamlit) incluye:

- **KPIs de negocio**: volumen, % positivo/negativo, calificación promedio, % de
  "detractores" (categoría NPS derivada de la calificación).
- **Tendencia de sentimiento en el tiempo** y **distribución de sentimiento**.
- **Temas de negocio** (tecnología, atención, costos, seguridad, tiempos,
  transacciones) cruzados con sentimiento.
- **Grafo de palabras interactivo**, alternable entre comentarios positivos/negativos.
- **Verbatims**: los comentarios más positivos y más negativos, citables tal cual.
- **Lectura para negocio**: bullets auto-generados con los focos de dolor de mayor
  volumen, como punto de partida de una recomendación.
- Filtros por banco, canal digital, sentimiento y rango de fechas.

## Estructura del proyecto

```
config/settings.yaml            configuración (fuente de datos, apps, escalas)
data/sample/                    dataset sintético versionado (demo sin fricción)
data/raw/, data/processed/      outputs del pipeline (gitignored, se regeneran)
src/customer_insights/
  ingestion/                    conectores: CSV, Play Store (interfaz común Connector)
  processing/                   limpieza, léxico de sentimiento, temas de negocio
  graph/                        grafo de co-ocurrencia de palabras
  pipeline.py                   orquestador end-to-end
app/dashboard.py                dashboard Streamlit (solo lectura de data/processed)
scripts/
  run_pipeline.py               CLI del pipeline
  generate_sample_data.py       generador del dataset sintético
tests/                          tests unitarios (limpieza, sentimiento, grafo)
```

## Instalación

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/run_pipeline.py
streamlit run app/dashboard.py
pytest tests/ -v   # opcional: correr la suite de tests
```

## Limitaciones y próximos pasos

- El motor léxico prioriza transparencia sobre precisión de punta; en un caso real
  se recomienda validar contra una muestra etiquetada manualmente y comparar contra
  el backend transformer antes de reportar métricas a negocio.
- La categorización de temas de negocio es por diccionario de palabras clave; con
  más volumen de datos reales conviene migrar a topic modeling (p. ej. BERTopic) y
  mantener el diccionario como capa de traducción/etiquetado legible.
- El conector de Play Store depende de la disponibilidad de `google-play-scraper`
  frente a cambios de Google Play; para producción se recomendaría una fuente más
  estable (API oficial de encuestas/NPS, data warehouse propio).
- Próximo paso natural: agregar un conector de encuestas reales (Typeform, Qualtrics,
  CSV de NPS interno) y una vista de tendencia por cohortes de clientes.
