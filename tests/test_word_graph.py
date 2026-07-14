import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from customer_insights.graph.word_graph import construir_grafo_coocurrencia, palabras_mas_influyentes


COMENTARIOS = [
    "la app esta muy lenta y se cae constantemente",
    "la aplicacion se cae y tiene errores todo el tiempo",
    "la app lenta hace que pierda tiempo cada dia",
    "el asesor fue amable y resolvio mi duda rapido",
    "el asesor amable resolvio todo en minutos",
]


def test_construir_grafo_genera_nodos_y_aristas():
    grafo = construir_grafo_coocurrencia(COMENTARIOS, min_frecuencia=2, max_nodos=20)
    assert grafo.number_of_nodes() > 0
    assert grafo.number_of_edges() > 0
    assert "lenta" in grafo.nodes or "cae" in grafo.nodes


def test_grafo_vacio_sin_comentarios():
    grafo = construir_grafo_coocurrencia([], min_frecuencia=2, max_nodos=20)
    assert grafo.number_of_nodes() == 0


def test_palabras_mas_influyentes_devuelve_columnas_esperadas():
    grafo = construir_grafo_coocurrencia(COMENTARIOS, min_frecuencia=2, max_nodos=20)
    tabla = palabras_mas_influyentes(grafo, top_n=5)
    assert list(tabla.columns) == ["palabra", "frecuencia", "grado", "intermediacion"]
    assert len(tabla) <= 5
