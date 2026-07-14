"""Analisis de sentimiento en español con dos backends intercambiables.

- LexiconSentimentAnalyzer (por defecto): basado en reglas y un lexico de
  polaridad. Sin dependencias pesadas, resultado 100% explicable palabra por
  palabra -> ideal para justificar hallazgos frente a negocio.
- TransformerSentimentAnalyzer (opcional): usa el modelo RoBERTuito de
  pysentimiento (BERT en español) para mayor precision. Requiere instalar
  requirements-optional.txt (pysentimiento + torch).

El pipeline usa SentimentAnalyzer como interfaz comun, de modo que cambiar de
backend es un cambio de una linea (ver pipeline.py).
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field

from .clean import quitar_acentos
from .lexicon_es import (
    INTENSIFICADORES,
    NEGADORES,
    PALABRAS_NEGATIVAS,
    PALABRAS_POSITIVAS,
    VENTANA_NEGACION,
)


@dataclass
class ResultadoSentimiento:
    etiqueta: str  # "positivo" | "neutral" | "negativo"
    polaridad: float  # -1.0 (muy negativo) a 1.0 (muy positivo)
    palabras_positivas: list[str] = field(default_factory=list)
    palabras_negativas: list[str] = field(default_factory=list)


class SentimentAnalyzer(abc.ABC):
    @abc.abstractmethod
    def analizar(self, texto: str) -> ResultadoSentimiento:
        raise NotImplementedError


class LexiconSentimentAnalyzer(SentimentAnalyzer):
    def __init__(self, umbral: float = 0.15):
        """umbral: valor absoluto de polaridad normalizada por debajo del cual se clasifica como neutral."""
        self.umbral = umbral

    @staticmethod
    def _tokenizar_preservando_negadores(texto: str) -> list[str]:
        texto = texto.lower()
        texto = quitar_acentos(texto)
        tokens = []
        palabra = []
        for ch in texto:
            if ch.isalpha():
                palabra.append(ch)
            else:
                if palabra:
                    tokens.append("".join(palabra))
                    palabra = []
        if palabra:
            tokens.append("".join(palabra))
        return tokens

    def analizar(self, texto: str) -> ResultadoSentimiento:
        tokens = self._tokenizar_preservando_negadores(texto or "")
        puntaje = 0.0
        pos_encontradas: list[str] = []
        neg_encontradas: list[str] = []

        for i, tok in enumerate(tokens):
            if tok not in PALABRAS_POSITIVAS and tok not in PALABRAS_NEGATIVAS:
                continue

            es_positiva = tok in PALABRAS_POSITIVAS
            peso = PALABRAS_POSITIVAS[tok] if es_positiva else PALABRAS_NEGATIVAS[tok]

            ventana_previa = tokens[max(0, i - VENTANA_NEGACION):i]
            negada = any(t in NEGADORES for t in ventana_previa)

            if ventana_previa and ventana_previa[-1] in INTENSIFICADORES:
                peso *= INTENSIFICADORES[ventana_previa[-1]]

            signo = 1.0 if es_positiva else -1.0
            if negada:
                signo *= -1.0

            puntaje += signo * peso
            if signo > 0:
                pos_encontradas.append(tok)
            else:
                neg_encontradas.append(tok)

        n_hits = len(pos_encontradas) + len(neg_encontradas)
        polaridad = max(-1.0, min(1.0, puntaje / (n_hits + 2))) if n_hits else 0.0

        if polaridad > self.umbral:
            etiqueta = "positivo"
        elif polaridad < -self.umbral:
            etiqueta = "negativo"
        else:
            etiqueta = "neutral"

        return ResultadoSentimiento(
            etiqueta=etiqueta,
            polaridad=round(polaridad, 4),
            palabras_positivas=pos_encontradas,
            palabras_negativas=neg_encontradas,
        )


class TransformerSentimentAnalyzer(SentimentAnalyzer):
    """Backend opcional de mayor precision basado en pysentimiento (RoBERTuito).

    Requiere `pip install -r requirements-optional.txt`. La carga del modelo
    es perezosa (solo ocurre si esta clase se instancia y se usa).
    """

    def __init__(self):
        try:
            from pysentimiento import create_analyzer
        except ImportError as exc:
            raise ImportError(
                "TransformerSentimentAnalyzer requiere 'pysentimiento' y 'torch'. "
                "Instala con: pip install -r requirements-optional.txt"
            ) from exc
        self._analyzer = create_analyzer(task="sentiment", lang="es")
        self._mapa_etiquetas = {"POS": "positivo", "NEG": "negativo", "NEU": "neutral"}

    def analizar(self, texto: str) -> ResultadoSentimiento:
        salida = self._analyzer.predict(texto or "")
        etiqueta = self._mapa_etiquetas.get(salida.output, "neutral")
        probas = salida.probas
        polaridad = probas.get("POS", 0.0) - probas.get("NEG", 0.0)
        return ResultadoSentimiento(etiqueta=etiqueta, polaridad=round(float(polaridad), 4))


def crear_analizador(backend: str = "lexicon") -> SentimentAnalyzer:
    if backend == "lexicon":
        return LexiconSentimentAnalyzer()
    if backend == "transformer":
        return TransformerSentimentAnalyzer()
    raise ValueError(f"Backend de sentimiento desconocido: {backend!r} (usar 'lexicon' o 'transformer')")
