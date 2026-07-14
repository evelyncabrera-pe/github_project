"""Orquesta el pipeline completo: ingestion -> limpieza -> sentimiento -> temas -> grafo.

Diseño: el pipeline se ejecuta como un paso batch offline (scripts/run_pipeline.py)
y guarda resultados tabulares en data/processed/. El dashboard de Streamlit
(app/dashboard.py) solo lee esos resultados: no vuelve a correr el modelo de
sentimiento ni el scraping en cada refresco, lo que lo hace rapido y liviano
de desplegar (no necesita cargar ningun modelo pesado en el servidor del dashboard).
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from .graph.word_graph import construir_grafo_coocurrencia, exportar_pyvis
from .ingestion.base import Connector
from .processing.sentiment import SentimentAnalyzer, crear_analizador
from .processing.topics import etiquetar_categoria_nps, etiquetar_tema_negocio

logger = logging.getLogger(__name__)

DIR_PROCESADOS = Path(__file__).resolve().parent.parent.parent / "data" / "processed"


def ejecutar_pipeline(
    conector: Connector,
    backend_sentimiento: str = "lexicon",
    escala_calificacion: float = 5,
    dir_salida: Path = DIR_PROCESADOS,
    **kwargs_extraccion,
) -> pd.DataFrame:
    """Corre el pipeline completo y guarda los artefactos en dir_salida.

    Devuelve el DataFrame procesado (una fila por comentario, con sentimiento,
    tema de negocio y categoria NPS) que alimenta el dashboard.
    """
    logger.info("1/5 Extrayendo datos con conector '%s'...", conector.nombre_fuente)
    df = conector.extraer(**kwargs_extraccion)
    if df.empty:
        raise RuntimeError("El conector no devolvio ningun registro. Revisa la fuente de datos.")

    logger.info("2/5 Calculando sentimiento (backend=%s) sobre %d comentarios...", backend_sentimiento, len(df))
    analizador: SentimentAnalyzer = crear_analizador(backend_sentimiento)
    resultados = df["comentario"].apply(analizador.analizar)
    df["sentimiento"] = resultados.apply(lambda r: r.etiqueta)
    df["polaridad"] = resultados.apply(lambda r: r.polaridad)

    logger.info("3/5 Etiquetando temas de negocio y categoria NPS...")
    df["temas_negocio"] = df["comentario"].apply(etiquetar_tema_negocio)
    df["categoria_nps"] = df["calificacion"].apply(lambda c: etiquetar_categoria_nps(c, escala_calificacion))

    dir_salida.mkdir(parents=True, exist_ok=True)
    ruta_dataset = dir_salida / "comentarios_procesados.parquet"
    df_export = df.copy()
    df_export["temas_negocio"] = df_export["temas_negocio"].apply(lambda temas: ", ".join(temas))
    df_export.to_parquet(ruta_dataset, index=False)
    df_export.to_csv(ruta_dataset.with_suffix(".csv"), index=False)
    logger.info("Dataset procesado guardado en %s", ruta_dataset)

    logger.info("4/5 Construyendo grafos de palabras (positivo / negativo)...")
    for etiqueta in ("positivo", "negativo"):
        comentarios_subset = df.loc[df["sentimiento"] == etiqueta, "comentario"].tolist()
        grafo = construir_grafo_coocurrencia(comentarios_subset)
        color = "#0ca30c" if etiqueta == "positivo" else "#d03b3b"
        exportar_pyvis(
            grafo,
            dir_salida / f"grafo_palabras_{etiqueta}.html",
            color_nodo=color,
            titulo=f"Grafo de palabras - comentarios {etiqueta}s",
        )

    logger.info("5/5 Pipeline finalizado. %d comentarios procesados.", len(df))
    return df
