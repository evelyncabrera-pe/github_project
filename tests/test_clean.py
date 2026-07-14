import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from customer_insights.processing.clean import limpiar_texto, tokenizar


def test_limpiar_texto_quita_acentos_y_puntuacion():
    assert limpiar_texto("¡La App está MUY lenta!") == "la app esta muy lenta"


def test_limpiar_texto_quita_urls_y_menciones():
    resultado = limpiar_texto("Revisa https://banco.com/soporte @BancoXYZ #queja")
    assert "http" not in resultado
    assert "@" not in resultado and "#" not in resultado


def test_tokenizar_quita_stopwords_y_palabras_cortas():
    tokens = tokenizar("la aplicacion del banco es muy lenta y no funciona")
    assert "la" not in tokens
    assert "del" not in tokens
    assert "lenta" in tokens
    assert "funciona" in tokens
