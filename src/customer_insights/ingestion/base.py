"""Interfaz comun para conectores de extraccion de texto (ingestion layer).

El objetivo de esta capa es desacoplar el pipeline de la fuente de datos: sin
importar si el texto viene de un dataset publico, del scraping de reseñas de
una app movil o de un futuro conector de encuestas/CRM, el resto del pipeline
(limpieza, sentimiento, grafo de palabras) siempre trabaja sobre el mismo
esquema tabular (DataFrame de pandas con las columnas de RegistroCliente).
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, fields

import pandas as pd


@dataclass(frozen=True)
class RegistroCliente:
    """Esquema estandar de un comentario/opinion de cliente en un canal digital."""

    id_resena: str
    fuente: str          # p.ej. "encuesta_nps", "play_store", "csv_publico"
    banco: str           # entidad / marca evaluada
    canal: str           # App Movil, Banca en Linea, Chat / Call Center, Sucursal...
    fecha: str           # ISO 8601 (YYYY-MM-DD)
    calificacion: float  # escala original (1-5 estrellas, 0-10 NPS, etc.)
    comentario: str      # texto libre del cliente

    @classmethod
    def columnas(cls) -> list[str]:
        return [f.name for f in fields(cls)]


class Connector(abc.ABC):
    """Contrato que debe cumplir cualquier fuente de datos del pipeline."""

    nombre_fuente: str = "generico"

    @abc.abstractmethod
    def extraer(self, **kwargs) -> pd.DataFrame:
        """Devuelve un DataFrame con las columnas de RegistroCliente."""
        raise NotImplementedError

    def _validar_esquema(self, df: pd.DataFrame) -> pd.DataFrame:
        faltantes = set(RegistroCliente.columnas()) - set(df.columns)
        if faltantes:
            raise ValueError(
                f"El conector '{self.nombre_fuente}' no genero las columnas requeridas: {faltantes}"
            )
        return df[RegistroCliente.columnas()]
