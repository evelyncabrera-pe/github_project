"""
Tests del pipeline ETL. Se corren con:  pytest scripts/test_etl_credito.py -v

Patrón estándar para testear pipelines de datos: no se testea "que corra sin
error" (muy débil) sino invariantes concretos sobre el resultado — shape,
ausencia de nulos donde no deberían existir, rangos válidos.
"""
from pathlib import Path

import pandas as pd
import pandera.pandas as pa
import pytest

from etl_credito import extract, transform, validar_esquema, ESQUEMA_ENTRADA

DATA_PATH = Path(__file__).parent.parent / "data" / "credito_solicitudes.csv"


@pytest.fixture(scope="module")
def df_crudo() -> pd.DataFrame:
    return extract(DATA_PATH)


@pytest.fixture(scope="module")
def df_transformado(df_crudo) -> pd.DataFrame:
    return transform(validar_esquema(df_crudo))


def test_extract_no_esta_vacio(df_crudo):
    assert len(df_crudo) > 0


def test_extract_falla_con_archivo_inexistente():
    with pytest.raises(FileNotFoundError):
        extract(Path("no_existe.csv"))


def test_esquema_rechaza_score_fuera_de_rango(df_crudo):
    df_invalido = df_crudo.copy()
    df_invalido.loc[0, "buro_score"] = 999  # fuera del rango válido 300-850
    with pytest.raises(pa.errors.SchemaErrors):
        ESQUEMA_ENTRADA.validate(df_invalido, lazy=True)


def test_transform_elimina_duplicados(df_transformado):
    assert df_transformado["solicitud_id"].duplicated().sum() == 0


def test_transform_no_deja_nulos_en_ingreso(df_transformado):
    assert df_transformado["ingreso_mensual"].isna().sum() == 0


def test_transform_dti_no_es_negativo(df_transformado):
    assert (df_transformado["dti"] >= 0).all()


def test_transform_agrega_columnas_esperadas(df_transformado):
    columnas_nuevas = {"dti", "monto_sobre_ingreso", "sin_historial_crediticio"}
    assert columnas_nuevas.issubset(df_transformado.columns)
