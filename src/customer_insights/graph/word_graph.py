"""Grafo de co-ocurrencia de palabras a partir de comentarios de clientes.

La idea de negocio: las palabras que aparecen juntas con frecuencia dentro de
los mismos comentarios (p.ej. "app" + "lenta", o "asesor" + "grosero") revelan
los temas que realmente le importan al cliente y como se conectan entre si.
Las palabras con mayor centralidad (mas conectadas al resto del grafo) suelen
ser los "temas raiz" de un dolor o una fortaleza percibida.
"""
from __future__ import annotations

from itertools import combinations
from pathlib import Path

import networkx as nx
import pandas as pd

from ..processing.clean import tokenizar


def construir_grafo_coocurrencia(
    comentarios: list[str],
    min_frecuencia: int = 3,
    max_nodos: int = 50,
) -> nx.Graph:
    """Construye un grafo no dirigido: nodos = palabras, aristas = co-ocurrencia en el mismo comentario.

    Args:
        comentarios: lista de textos crudos (se limpian y tokenizan internamente).
        min_frecuencia: frecuencia minima de una palabra para entrar al grafo (reduce ruido).
        max_nodos: numero maximo de palabras a incluir (mantiene el grafo legible).
    """
    tokens_por_comentario = [tokenizar(c) for c in comentarios]

    frecuencias: dict[str, int] = {}
    for tokens in tokens_por_comentario:
        for tok in set(tokens):
            frecuencias[tok] = frecuencias.get(tok, 0) + 1

    vocabulario = {
        palabra
        for palabra, frecuencia in sorted(frecuencias.items(), key=lambda kv: kv[1], reverse=True)
        if frecuencia >= min_frecuencia
    }
    vocabulario = set(list(sorted(vocabulario, key=lambda p: frecuencias[p], reverse=True))[:max_nodos])

    grafo = nx.Graph()
    for palabra in vocabulario:
        grafo.add_node(palabra, frecuencia=frecuencias[palabra])

    for tokens in tokens_por_comentario:
        presentes = sorted(set(tokens) & vocabulario)
        for palabra_a, palabra_b in combinations(presentes, 2):
            if grafo.has_edge(palabra_a, palabra_b):
                grafo[palabra_a][palabra_b]["peso"] += 1
            else:
                grafo.add_edge(palabra_a, palabra_b, peso=1)

    grafo.remove_nodes_from(list(nx.isolates(grafo)))
    return grafo


def palabras_mas_influyentes(grafo: nx.Graph, top_n: int = 15) -> pd.DataFrame:
    """Ranking de palabras por frecuencia y centralidad (que tan 'puente' es la palabra en el grafo)."""
    if grafo.number_of_nodes() == 0:
        return pd.DataFrame(columns=["palabra", "frecuencia", "grado", "intermediacion"])

    grados = dict(grafo.degree(weight="peso"))
    intermediacion = nx.betweenness_centrality(grafo, weight="peso") if grafo.number_of_nodes() > 2 else {}

    filas = [
        {
            "palabra": nodo,
            "frecuencia": datos["frecuencia"],
            "grado": grados.get(nodo, 0),
            "intermediacion": round(intermediacion.get(nodo, 0.0), 4),
        }
        for nodo, datos in grafo.nodes(data=True)
    ]
    df = pd.DataFrame(filas).sort_values("frecuencia", ascending=False).reset_index(drop=True)
    return df.head(top_n)


def exportar_pyvis(
    grafo: nx.Graph,
    ruta_html: str | Path,
    color_nodo: str = "#4C78A8",
    titulo: str = "Grafo de palabras",
) -> Path:
    """Genera un HTML interactivo (arrastrable/zoom) del grafo con pyvis."""
    from pyvis.network import Network

    # cdn_resources="in_line" empaqueta vis-network.js dentro del HTML: el grafo
    # funciona sin conexion a internet y sin depender de que un CDN externo responda.
    red = Network(height="600px", width="100%", bgcolor="#ffffff", font_color="#222222", notebook=False, cdn_resources="in_line")
    red.heading = titulo

    if grafo.number_of_nodes() == 0:
        red.add_node("sin_datos", label="Sin datos suficientes", color="#cccccc")
    else:
        frecuencias = nx.get_node_attributes(grafo, "frecuencia")
        max_frec = max(frecuencias.values()) if frecuencias else 1
        for nodo, datos in grafo.nodes(data=True):
            tamano = 12 + 28 * (datos["frecuencia"] / max_frec)
            red.add_node(nodo, label=nodo, size=tamano, color=color_nodo, title=f"frecuencia: {datos['frecuencia']}")
        for origen, destino, datos in grafo.edges(data=True):
            red.add_edge(origen, destino, value=datos["peso"], title=f"co-ocurrencias: {datos['peso']}")

    red.repulsion(node_distance=160, spring_length=180)
    ruta_html = Path(ruta_html)
    ruta_html.parent.mkdir(parents=True, exist_ok=True)
    red.write_html(str(ruta_html), notebook=False, open_browser=False)
    return ruta_html
