"""Conector para datasets publicos o propios entregados como CSV.

Sirve tanto para el dataset sintetico de muestra (data/sample) como para
cualquier dataset publico real (encuestas de satisfaccion, NPS, exports de
CRM) siempre que se mapeen sus columnas al esquema estandar de RegistroCliente.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .base import Connector, RegistroCliente


class CSVConnector(Connector):
    nombre_fuente = "csv_publico"

    def __init__(self, ruta: str | Path, mapeo_columnas: dict[str, str] | None = None, fuente: str | None = None):
        """
        Args:
            ruta: ruta al archivo CSV.
            mapeo_columnas: diccionario {columna_origen: columna_esquema}. Si el CSV
                ya usa los nombres de RegistroCliente (banco, canal, fecha,
                calificacion, comentario, id_resena) se puede omitir.
            fuente: etiqueta a usar en la columna 'fuente' (por defecto, el nombre del archivo).
        """
        self.ruta = Path(ruta)
        self.mapeo_columnas = mapeo_columnas or {}
        self.fuente = fuente or self.ruta.stem

    def extraer(self, **kwargs) -> pd.DataFrame:
        df = pd.read_csv(self.ruta)
        if self.mapeo_columnas:
            df = df.rename(columns=self.mapeo_columnas)

        if "id_resena" not in df.columns:
            df["id_resena"] = [f"{self.fuente}_{i}" for i in range(len(df))]
        if "fuente" not in df.columns:
            df["fuente"] = self.fuente

        df["id_resena"] = df["id_resena"].astype(str)
        df["calificacion"] = pd.to_numeric(df["calificacion"], errors="coerce")
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce").dt.strftime("%Y-%m-%d")
        df["comentario"] = df["comentario"].astype(str).str.strip()
        df = df.dropna(subset=["comentario", "fecha"])
        df = df[df["comentario"].str.len() > 0]

        return self._validar_esquema(df)
