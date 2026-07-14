"""Dashboard de Streamlit: Voz del Cliente en Banca Digital.

Lee unicamente los artefactos ya calculados por el pipeline (data/processed/).
No carga ningun modelo de NLP en tiempo de ejecucion, por lo que es liviano de
desplegar (Streamlit Community Cloud, Render, etc.).

Correr con: streamlit run app/dashboard.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from customer_insights.graph.word_graph import construir_grafo_coocurrencia, palabras_mas_influyentes  # noqa: E402
from customer_insights.ingestion.csv_loader import CSVConnector  # noqa: E402
from customer_insights.pipeline import ejecutar_pipeline  # noqa: E402

DIR_PROCESADOS = RAIZ / "data" / "processed"
RUTA_DATASET = DIR_PROCESADOS / "comentarios_procesados.csv"
RUTA_MUESTRA = RAIZ / "data" / "sample" / "resenas_banca_muestra.csv"


def asegurar_datos_procesados() -> None:
    """Genera data/processed/* con el dataset de muestra si aun no existen.

    En un despliegue en Streamlit Community Cloud el repo se clona sin los
    artefactos de data/processed (estan en .gitignore porque se regeneran).
    Esto hace que la demo publica se auto-inicialice en el primer arranque,
    sin depender de que alguien corra el pipeline manualmente antes.
    """
    if RUTA_DATASET.exists():
        return
    with st.spinner("Generando datos de la demo por primera vez (unos segundos)..."):
        conector = CSVConnector(RUTA_MUESTRA, fuente="encuesta_nps")
        ejecutar_pipeline(conector, backend_sentimiento="lexicon", escala_calificacion=5, dir_salida=DIR_PROCESADOS)

# --- Paleta validada (ver skill de dataviz): status para sentimiento, categorica de orden fijo para dimensiones ---
COLOR_SENTIMIENTO = {"positivo": "#0ca30c", "neutral": "#898781", "negativo": "#d03b3b"}
PALETA_CATEGORICA = ["#2a78d6", "#1baf7a", "#eda100", "#008300", "#4a3aa7", "#e34948", "#e87ba4", "#eb6834"]
ORDEN_SENTIMIENTO = ["positivo", "neutral", "negativo"]

st.set_page_config(page_title="Voz del Cliente | Banca Digital", page_icon="💬", layout="wide")


@st.cache_data
def cargar_datos() -> pd.DataFrame:
    df = pd.read_csv(RUTA_DATASET, parse_dates=["fecha"])
    return df


def color_categorico(valores: list[str]) -> dict[str, str]:
    valores_unicos = sorted(set(valores))
    return {v: PALETA_CATEGORICA[i % len(PALETA_CATEGORICA)] for i, v in enumerate(valores_unicos)}


def render_grafo(comentarios: list[str], etiqueta: str) -> None:
    color = COLOR_SENTIMIENTO[etiqueta]
    grafo = construir_grafo_coocurrencia(comentarios, min_frecuencia=2, max_nodos=40)
    if grafo.number_of_nodes() == 0:
        st.info("No hay suficientes comentarios en este filtro para construir un grafo de palabras.")
        return

    from pyvis.network import Network
    import networkx as nx

    red = Network(height="520px", width="100%", bgcolor="#ffffff", font_color="#0b0b0b", notebook=False, cdn_resources="in_line")
    frecuencias = nx.get_node_attributes(grafo, "frecuencia")
    max_frec = max(frecuencias.values()) if frecuencias else 1
    for nodo, datos in grafo.nodes(data=True):
        tamano = 12 + 28 * (datos["frecuencia"] / max_frec)
        red.add_node(nodo, label=nodo, size=tamano, color=color, title=f"frecuencia: {datos['frecuencia']}")
    for origen, destino, datos in grafo.edges(data=True):
        red.add_edge(origen, destino, value=datos["peso"], title=f"co-ocurrencias: {datos['peso']}")
    red.repulsion(node_distance=150, spring_length=170)

    ruta_html = DIR_PROCESADOS / f"_grafo_tmp_{etiqueta}.html"
    red.write_html(str(ruta_html), notebook=False, open_browser=False)
    components.html(ruta_html.read_text(encoding="utf-8"), height=540, scrolling=True)

    st.caption("Tamaño del nodo = frecuencia de la palabra. Grosor de arista = veces que dos palabras aparecen juntas en el mismo comentario.")
    tabla = palabras_mas_influyentes(grafo, top_n=10)
    st.dataframe(
        tabla.rename(columns={
            "palabra": "Palabra", "frecuencia": "Frecuencia", "grado": "Grado (conexiones)", "intermediacion": "Centralidad (puente entre temas)",
        }),
        hide_index=True,
        use_container_width=True,
    )


def main() -> None:
    asegurar_datos_procesados()
    df = cargar_datos()

    st.title("💬 Voz del Cliente en Banca Digital")
    st.caption(
        "Análisis de sentimiento y grafo de palabras sobre comentarios de clientes en canales digitales "
        "(app móvil, banca en línea, chat/call center). Pipeline reproducible + dashboard interactivo."
    )

    # --- Filtros ---
    with st.sidebar:
        st.header("Filtros")
        bancos = st.multiselect("Banco / entidad", sorted(df["banco"].unique()), default=sorted(df["banco"].unique()))
        canales = st.multiselect("Canal digital", sorted(df["canal"].unique()), default=sorted(df["canal"].unique()))
        sentimientos = st.multiselect("Sentimiento", ORDEN_SENTIMIENTO, default=ORDEN_SENTIMIENTO)
        fecha_min, fecha_max = df["fecha"].min().date(), df["fecha"].max().date()
        rango_fechas = st.slider("Rango de fechas", min_value=fecha_min, max_value=fecha_max, value=(fecha_min, fecha_max))

    filtrado = df[
        df["banco"].isin(bancos)
        & df["canal"].isin(canales)
        & df["sentimiento"].isin(sentimientos)
        & df["fecha"].dt.date.between(*rango_fechas)
    ]

    if filtrado.empty:
        st.info("No hay comentarios que coincidan con los filtros seleccionados.")
        st.stop()

    # --- KPIs ---
    total = len(filtrado)
    pct = lambda etiqueta: 100 * (filtrado["sentimiento"] == etiqueta).sum() / total
    pct_detractores = 100 * (filtrado["categoria_nps"] == "Detractor").sum() / total

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Comentarios analizados", f"{total:,}")
    c2.metric("% Positivos", f"{pct('positivo'):.0f}%")
    c3.metric("% Negativos", f"{pct('negativo'):.0f}%")
    c4.metric("Calificación promedio", f"{filtrado['calificacion'].mean():.1f} / 5")
    c5.metric("% Detractores (NPS)", f"{pct_detractores:.0f}%")

    st.divider()

    col_izq, col_der = st.columns([3, 2])

    with col_izq:
        st.subheader("Tendencia de sentimiento en el tiempo")
        serie = (
            filtrado.assign(mes=filtrado["fecha"].dt.to_period("M").dt.to_timestamp())
            .groupby(["mes", "sentimiento"])
            .size()
            .reset_index(name="conteo")
        )
        fig = go.Figure()
        for etiqueta in ORDEN_SENTIMIENTO:
            sub = serie[serie["sentimiento"] == etiqueta]
            fig.add_trace(
                go.Scatter(
                    x=sub["mes"], y=sub["conteo"], mode="lines", name=etiqueta.capitalize(),
                    line=dict(color=COLOR_SENTIMIENTO[etiqueta], width=2),
                )
            )
        fig.update_layout(
            height=340, margin=dict(l=10, r=10, t=10, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            yaxis_title="Comentarios", xaxis_title=None,
            plot_bgcolor="#fcfcfb", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_der:
        st.subheader("Distribución de sentimiento")
        conteo_sent = filtrado["sentimiento"].value_counts().reindex(ORDEN_SENTIMIENTO).fillna(0)
        fig = go.Figure(
            go.Bar(
                x=conteo_sent.values, y=[s.capitalize() for s in conteo_sent.index], orientation="h",
                marker_color=[COLOR_SENTIMIENTO[s] for s in conteo_sent.index],
                text=conteo_sent.values, textposition="outside",
            )
        )
        fig.update_layout(
            height=340, margin=dict(l=10, r=10, t=10, b=10),
            xaxis_title="Comentarios", showlegend=False,
            plot_bgcolor="#fcfcfb", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Temas de negocio detectados")
    temas_explotado = filtrado.assign(tema=filtrado["temas_negocio"].str.split(", ")).explode("tema")
    tabla_temas = temas_explotado.groupby(["tema", "sentimiento"]).size().reset_index(name="conteo")
    fig = go.Figure()
    for etiqueta in ORDEN_SENTIMIENTO:
        sub = tabla_temas[tabla_temas["sentimiento"] == etiqueta]
        fig.add_trace(
            go.Bar(y=sub["tema"], x=sub["conteo"], name=etiqueta.capitalize(), orientation="h", marker_color=COLOR_SENTIMIENTO[etiqueta])
        )
    fig.update_layout(
        barmode="stack", height=360, margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        xaxis_title="Comentarios", plot_bgcolor="#fcfcfb", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    st.subheader("Grafo de palabras")
    st.caption("Explora las palabras que más se conectan entre sí dentro de los comentarios positivos vs. negativos.")
    tab_neg, tab_pos = st.tabs(["🔴 Comentarios negativos", "🟢 Comentarios positivos"])
    with tab_neg:
        render_grafo(filtrado.loc[filtrado["sentimiento"] == "negativo", "comentario"].tolist(), "negativo")
    with tab_pos:
        render_grafo(filtrado.loc[filtrado["sentimiento"] == "positivo", "comentario"].tolist(), "positivo")

    st.divider()

    st.subheader("Comentarios representativos (verbatims)")
    col_neg, col_pos = st.columns(2)
    with col_neg:
        st.markdown("**Más negativos**")
        peores = filtrado.nsmallest(5, "polaridad")[["banco", "canal", "fecha", "comentario"]]
        for _, fila in peores.iterrows():
            st.markdown(f"> {fila['comentario']}")
            st.caption(f"{fila['banco']} · {fila['canal']} · {fila['fecha'].date()}")
    with col_pos:
        st.markdown("**Más positivos**")
        mejores = filtrado.nlargest(5, "polaridad")[["banco", "canal", "fecha", "comentario"]]
        for _, fila in mejores.iterrows():
            st.markdown(f"> {fila['comentario']}")
            st.caption(f"{fila['banco']} · {fila['canal']} · {fila['fecha'].date()}")

    st.divider()

    st.subheader("Lectura para negocio")
    temas_negativos = (
        temas_explotado[temas_explotado["sentimiento"] == "negativo"]["tema"].value_counts().head(3)
    )
    if not temas_negativos.empty:
        lineas = [f"- **{tema}**: {conteo} menciones negativas — priorizar como foco de mejora." for tema, conteo in temas_negativos.items()]
        st.markdown("**Focos de dolor detectados (mayor volumen de menciones negativas):**\n\n" + "\n".join(lineas))
    st.caption(
        "Nota metodológica: el sentimiento se calcula con un motor léxico explicable en español "
        "(ver processing/sentiment.py). Para mayor precisión puede activarse un backend basado en "
        "transformers (pysentimiento) — ver README."
    )


if __name__ == "__main__":
    main()
