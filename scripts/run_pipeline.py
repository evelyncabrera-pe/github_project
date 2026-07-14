"""CLI para correr el pipeline de extraccion -> sentimiento -> grafo de palabras.

Ejemplos:
    python scripts/run_pipeline.py
    python scripts/run_pipeline.py --fuente muestra
    python scripts/run_pipeline.py --fuente play_store
    python scripts/run_pipeline.py --fuente csv --csv-path data/raw/mi_dataset.csv
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from customer_insights.ingestion.csv_loader import CSVConnector
from customer_insights.ingestion.play_store import PlayStoreConnector
from customer_insights.pipeline import ejecutar_pipeline

RAIZ = Path(__file__).resolve().parent.parent


def cargar_config() -> dict:
    with open(RAIZ / "config" / "settings.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    config = cargar_config()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fuente",
        choices=["muestra", "play_store", "csv"],
        default=config.get("fuente_por_defecto", "muestra"),
        help="Fuente de datos a usar.",
    )
    parser.add_argument(
        "--csv-path",
        default=None,
        help="Ruta al CSV a usar cuando --fuente csv.",
    )
    parser.add_argument(
        "--backend-sentimiento",
        choices=["lexicon", "transformer"],
        default=config.get("backend_sentimiento", "lexicon"),
    )
    args = parser.parse_args()

    if args.fuente == "muestra":
        conector = CSVConnector(
            RAIZ / "data" / "sample" / "resenas_banca_muestra.csv",
            fuente="encuesta_nps",
        )
        escala = 5
    elif args.fuente == "play_store":
        conector = PlayStoreConnector(
            apps=config["apps_play_store"],
            lang=config.get("idioma_resenas", "es"),
            country=config.get("pais_resenas", "mx"),
            max_resenas_por_app=config.get("max_resenas_por_app", 200),
        )
        escala = 5
    elif args.fuente == "csv":
        if not args.csv_path:
            parser.error("--csv-path es requerido cuando --fuente csv")
        conector = CSVConnector(args.csv_path, fuente="csv_publico")
        escala = config.get("escala_calificacion", 5)
    else:
        parser.error(f"Fuente no soportada: {args.fuente}")
        return

    ejecutar_pipeline(
        conector,
        backend_sentimiento=args.backend_sentimiento,
        escala_calificacion=escala,
    )


if __name__ == "__main__":
    main()
