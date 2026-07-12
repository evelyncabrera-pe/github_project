"""
Pipeline ETL de referencia para el dataset de solicitudes de crédito.

Diseñado como se vería en producción: funciones puras y testeables
(extract/transform/load separadas), validación de esquema explícita,
logging estructurado y una CLI para poder correrlo como job programado
(cron, Airflow, etc.) sin depender de un notebook.

Uso como script:
    python scripts/etl_credito.py --input data/credito_solicitudes.csv --output data/credito_procesado.csv

Uso como librería (como se usa en notebooks/08_automatizacion_pipelines.ipynb):
    from etl_credito import extract, transform, load, validar_esquema
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import pandera.pandas as pa
from pandera.pandas import Column, Check

logger = logging.getLogger("etl_credito")


# --- 1. Esquema de validación: contrato explícito de qué forma deben tener los datos ---
ESQUEMA_ENTRADA = pa.DataFrameSchema({
    "solicitud_id": Column(str, Check.str_startswith("CR-"), nullable=False),
    "buro_score": Column(float, Check.in_range(300, 850), nullable=True),
    "ingreso_mensual": Column(float, Check.greater_than(0), nullable=True),
    "monto_solicitado": Column(float, Check.greater_than(0), nullable=False),
    "default_90d": Column(int, Check.isin([0, 1]), nullable=False),
})


def extract(path: Path) -> pd.DataFrame:
    """Lee el CSV crudo. Falla ruidosamente si el archivo no existe."""
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de entrada: {path}")
    df = pd.read_csv(path, parse_dates=["fecha_solicitud"])
    logger.info(f"Extract: {len(df):,} filas leídas de {path.name}")
    return df


def validar_esquema(df: pd.DataFrame) -> pd.DataFrame:
    """Valida el esquema ANTES de transformar. Falla rápido con un error legible."""
    try:
        return ESQUEMA_ENTRADA.validate(df, lazy=True)
    except pa.errors.SchemaErrors as e:
        logger.error(f"Validación de esquema falló:\n{e.failure_cases}")
        raise


def transform(df: pd.DataFrame) -> pd.DataFrame:
    """Limpieza y feature engineering reproducibles (misma lógica que el EDA del módulo 05)."""
    df = df.drop_duplicates(subset="solicitud_id").copy()
    df["ingreso_mensual"] = df["ingreso_mensual"].fillna(
        df.groupby("sector", observed=True)["ingreso_mensual"].transform("median")
    )
    df["sin_historial_crediticio"] = df["buro_score"].isna().astype(int)
    df["dti"] = df["deuda_actual"] / (df["ingreso_mensual"] + 1)
    df["monto_sobre_ingreso"] = df["monto_solicitado"] / (df["ingreso_mensual"] + 1)
    logger.info(f"Transform: {len(df):,} filas tras limpieza y feature engineering")
    return df


def load(df: pd.DataFrame, path: Path) -> None:
    """Escribe el resultado. En un pipeline real, aquí iría un INSERT a un warehouse."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    logger.info(f"Load: {len(df):,} filas escritas en {path}")


def ejecutar_pipeline(path_entrada: Path, path_salida: Path) -> pd.DataFrame:
    """Orquesta extract -> validate -> transform -> load. Punto de entrada único y testeable."""
    df_crudo = extract(path_entrada)
    df_validado = validar_esquema(df_crudo)
    df_transformado = transform(df_validado)
    load(df_transformado, path_salida)
    return df_transformado


def _configurar_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> None:
    import click

    @click.command()
    @click.option("--input", "path_entrada", required=True, type=click.Path(exists=True, path_type=Path))
    @click.option("--output", "path_salida", required=True, type=click.Path(path_type=Path))
    def cli(path_entrada: Path, path_salida: Path) -> None:
        """Corre el pipeline ETL de solicitudes de crédito."""
        _configurar_logging()
        ejecutar_pipeline(path_entrada, path_salida)

    cli()


if __name__ == "__main__":
    main()
