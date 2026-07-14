"""Normalizacion y tokenizacion de texto en español.

Se evita depender de descargas externas (p.ej. corpora de NLTK) para que el
pipeline funcione sin conexion a internet: el listado de stopwords y las
reglas de limpieza estan autocontenidas en este modulo.
"""
from __future__ import annotations

import re
import unicodedata

STOPWORDS_ES = {
    "a", "al", "algo", "algunas", "algunos", "ante", "antes", "como", "con", "contra",
    "cual", "cuando", "de", "del", "desde", "donde", "durante", "e", "el", "ella",
    "ellas", "ellos", "en", "entre", "era", "erais", "eran", "eras", "eres", "es",
    "esa", "esas", "ese", "eso", "esos", "esta", "estaba", "estamos", "estan",
    "estar", "este", "esto", "estos", "fue", "fueron", "fui", "fuimos", "ha", "habia",
    "han", "hasta", "hay", "he", "la", "las", "le", "les", "lo", "los", "mas", "me",
    "mi", "mia", "mias", "mientras", "mio", "mios", "mis", "mucho", "muchos", "muy",
    "nada", "ni", "no", "nos", "nosotras", "nosotros", "nuestra", "nuestras",
    "nuestro", "nuestros", "o", "os", "otra", "otras", "otro", "otros", "para",
    "pero", "poco", "por", "porque", "que", "quien", "quienes", "se", "sea", "sean",
    "sentid", "ser", "si", "sido", "siendo", "sin", "sobre", "sois", "somos", "son",
    "soy", "su", "sus", "suya", "suyas", "suyo", "suyos", "tambien", "tanto", "te",
    "tenia", "tener", "teneis", "tenemos", "tengo", "ti", "tiene", "tienen", "todo",
    "todos", "tu", "tus", "tuya", "tuyas", "tuyo", "tuyos", "un", "una", "uno",
    "unos", "usted", "ustedes", "vosotras", "vosotros", "vuestra", "vuestras",
    "vuestro", "vuestros", "y", "ya", "yo", "he", "eh", "asi", "aun",
    # ruido especifico de reseñas de apps / banca que no aporta señal tematica
    "app", "aplicacion", "banco", "bien", "mal", "cosa", "vez", "veces", "dia", "dias",
}

_RE_URL = re.compile(r"https?://\S+|www\.\S+")
_RE_MENCION = re.compile(r"[@#]\w+")
_RE_NO_ALFA = re.compile(r"[^a-zñ\s]")
_RE_ESPACIOS = re.compile(r"\s+")


def quitar_acentos(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def limpiar_texto(texto: str) -> str:
    """Normaliza un comentario: minusculas, sin acentos, sin URLs/menciones/numeros/puntuacion."""
    if not isinstance(texto, str):
        return ""
    texto = texto.lower()
    texto = _RE_URL.sub(" ", texto)
    texto = _RE_MENCION.sub(" ", texto)
    texto = quitar_acentos(texto)
    texto = _RE_NO_ALFA.sub(" ", texto)
    texto = _RE_ESPACIOS.sub(" ", texto).strip()
    return texto


def tokenizar(texto: str, quitar_stopwords: bool = True, longitud_minima: int = 3) -> list[str]:
    """Convierte un comentario en una lista de tokens listos para sentimiento/grafo."""
    texto_limpio = limpiar_texto(texto)
    tokens = texto_limpio.split()
    tokens = [t for t in tokens if len(t) >= longitud_minima]
    if quitar_stopwords:
        tokens = [t for t in tokens if t not in STOPWORDS_ES]
    return tokens
