import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from customer_insights.processing.sentiment import LexiconSentimentAnalyzer


def test_comentario_claramente_positivo():
    analizador = LexiconSentimentAnalyzer()
    resultado = analizador.analizar("La app es excelente, muy rapida y el asesor fue muy amable.")
    assert resultado.etiqueta == "positivo"
    assert resultado.polaridad > 0


def test_comentario_claramente_negativo():
    analizador = LexiconSentimentAnalyzer()
    resultado = analizador.analizar("Pesimo servicio, el asesor fue grosero y la app tiene errores constantes.")
    assert resultado.etiqueta == "negativo"
    assert resultado.polaridad < 0


def test_negacion_invierte_polaridad():
    analizador = LexiconSentimentAnalyzer()
    positivo = analizador.analizar("El asesor resolvio mi problema.")
    negado = analizador.analizar("El asesor no resolvio mi problema.")
    assert positivo.polaridad > negado.polaridad


def test_comentario_neutral_sin_palabras_del_lexico():
    analizador = LexiconSentimentAnalyzer()
    resultado = analizador.analizar("Las comisiones son similares a las de otros bancos.")
    assert resultado.etiqueta == "neutral"
