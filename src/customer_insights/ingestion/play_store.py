"""Conector de extraccion en vivo de resenas de apps en Google Play Store.

Representa la fuente "aplicativos" del pipeline: reseñas reales y publicas de
apps de banca movil, con calificacion (1-5) y comentario libre, que funcionan
como una señal de voz del cliente equivalente a una encuesta de satisfaccion.

Requiere conexion a internet. Si Google Play cambia su markup o bloquea la
extraccion, el pipeline sigue funcionando con el dataset de muestra o con
cualquier CSVConnector.
"""
from __future__ import annotations

import logging

import pandas as pd

from .base import Connector

logger = logging.getLogger(__name__)


class PlayStoreConnector(Connector):
    nombre_fuente = "play_store"

    def __init__(self, apps: dict[str, str], lang: str = "es", country: str = "mx", max_resenas_por_app: int = 200):
        """
        Args:
            apps: diccionario {nombre_visible_banco: app_id_de_play_store}.
                Ejemplo: {"BBVA": "com.bbva.bbvacontigo", "Nubank": "com.nu.production"}
            lang: idioma ISO 639-1 de las reseñas a extraer.
            country: pais ISO 3166 (afecta la tienda consultada).
            max_resenas_por_app: limite de reseñas a traer por app (evita scraping excesivo).
        """
        self.apps = apps
        self.lang = lang
        self.country = country
        self.max_resenas_por_app = max_resenas_por_app

    def extraer(self, **kwargs) -> pd.DataFrame:
        from google_play_scraper import Sort, reviews

        filas = []
        for banco, app_id in self.apps.items():
            try:
                resultados, _ = reviews(
                    app_id,
                    lang=self.lang,
                    country=self.country,
                    sort=Sort.NEWEST,
                    count=self.max_resenas_por_app,
                )
            except Exception as exc:  # la red o Play Store pueden fallar; no debe tumbar el pipeline
                logger.warning("No se pudieron extraer reseñas de %s (%s): %s", banco, app_id, exc)
                continue

            for r in resultados:
                filas.append(
                    {
                        "id_resena": r.get("reviewId"),
                        "fuente": self.nombre_fuente,
                        "banco": banco,
                        "canal": "App Movil",
                        "fecha": r["at"].strftime("%Y-%m-%d") if r.get("at") else None,
                        "calificacion": r.get("score"),
                        "comentario": (r.get("content") or "").strip(),
                    }
                )

        df = pd.DataFrame(filas)
        if df.empty:
            return df
        df = df.dropna(subset=["comentario", "fecha"])
        df = df[df["comentario"].str.len() > 0]
        return self._validar_esquema(df)
