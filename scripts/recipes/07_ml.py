CELLS = [
{"type": "markdown", "source": r"""
# 07 · Modelos predictivos y Machine Learning

Este es el módulo central: de EDA a modelos que se pueden defender frente a
un equipo de riesgo o de producto. Cubrimos clasificación, regresión,
clustering y series de tiempo con `scikit-learn`, con el énfasis puesto en lo
que un analista senior no puede saltarse: **splits correctos, pipelines sin
fuga de datos (leakage), y métricas que importan al negocio, no solo
accuracy.**

**Dataset principal:** `credito_solicitudes.csv` (clasificación de default,
regresión de tasa de interés, clustering de segmentos). Series de tiempo con
`precios_acciones_tech.csv`.

## Contenido
1. Split correcto y el problema de data leakage
2. Pipeline de preprocesamiento con `ColumnTransformer`
3. Clasificación: Regresión Logística vs. Random Forest — métricas más allá de accuracy
4. Validación cruzada y búsqueda de hiperparámetros
5. Regresión: predecir la tasa de interés
6. Clustering: segmentación de clientes con K-Means
7. Series de tiempo: forecasting con baseline + Gradient Boosting
8. Interpretabilidad: importancia de features
9. Checklist anti-leakage
"""},

{"type": "code", "source": r"""
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold, RandomizedSearchCV
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import (
    roc_auc_score, roc_curve, precision_recall_curve, confusion_matrix,
    classification_report, mean_absolute_error, mean_squared_error, r2_score,
)

pd.set_option("display.width", 120)
RNG_SEED = 42

df = pd.read_csv("data/credito_solicitudes.csv", parse_dates=["fecha_solicitud"]).drop_duplicates(subset="solicitud_id")
df["ingreso_mensual"] = df["ingreso_mensual"].fillna(df.groupby("sector", observed=True)["ingreso_mensual"].transform("median"))
df["sin_historial_crediticio"] = df["buro_score"].isna().astype(int)
df["dti"] = df["deuda_actual"] / (df["ingreso_mensual"] + 1)
df["monto_sobre_ingreso"] = df["monto_solicitado"] / (df["ingreso_mensual"] + 1)
df.shape
"""},

{"type": "markdown", "source": r"""
## 1. Split correcto y data leakage

**Leakage** = información del futuro (o del target) se cuela en los
features. Dos formas comunes:

1. **Split aleatorio en datos con estructura temporal** (predices el pasado
   con el futuro) — para series/eventos con fecha, el split debe ser
   **temporal**.
2. **Preprocesar (imputar, escalar) ANTES de separar train/test** — el
   escalador "ve" estadísticas del test set, inflando artificialmente el
   desempeño reportado.

Aquí `default_90d` no tiene dependencia temporal fuerte entre solicitudes
(son eventos ~independientes), así que un split aleatorio estratificado es
razonable — pero se justifica explícitamente, no se asume.
"""},

{"type": "code", "source": r"""
features_num = ["edad", "antiguedad_laboral_anios", "antiguedad_empresa_anios", "ingreso_mensual",
                 "deuda_actual", "num_creditos_previos", "buro_score", "monto_solicitado",
                 "plazo_meses", "dti", "monto_sobre_ingreso", "sin_historial_crediticio"]
features_cat = ["sector"]
target = "default_90d"

X = df[features_num + features_cat].copy()
X["buro_score"] = X["buro_score"].fillna(X["buro_score"].median())  # imputación DENTRO del pipeline sería mejor aún (ver nota)
y = df[target]

# stratify=y: mantiene la MISMA proporción de default en train y test (clave con clases desbalanceadas)
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.25, random_state=RNG_SEED, stratify=y
)
print(f"Train: {X_train.shape[0]:,} filas | tasa default: {y_train.mean():.2%}")
print(f"Test:  {X_test.shape[0]:,} filas | tasa default: {y_test.mean():.2%}")
"""},

{"type": "markdown", "source": r"""
> **Nota:** aquí imputamos `buro_score` antes del split por simplicidad de
> ejemplo. En producción, la imputación (con `SimpleImputer`) debe ir **dentro
> del `Pipeline`**, ajustada solo con `X_train`, para que ningún estadístico
> del test set influya en el train — ver sección 2.
"""},

{"type": "markdown", "source": r"""
## 2. Pipeline de preprocesamiento con `ColumnTransformer`

Un `Pipeline` de sklearn encapsula preprocesamiento + modelo en un solo
objeto: se ajusta (`fit`) solo con train, y garantiza que exactamente la
misma transformación se aplique en test/producción — la forma correcta de
evitar leakage por construcción.
"""},

{"type": "code", "source": r"""
from sklearn.impute import SimpleImputer

preprocesador = ColumnTransformer(transformers=[
    ("num", Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ]), features_num),
    ("cat", OneHotEncoder(handle_unknown="ignore"), features_cat),
])

# El escalador/imputador se AJUSTA (fit) solo dentro de cada fold de CV o en X_train,
# nunca viendo X_test -> Pipeline lo garantiza automáticamente.
preprocesador
"""},

{"type": "markdown", "source": r"""
## 3. Clasificación: Regresión Logística vs. Random Forest

Con clases desbalanceadas (17.8% default), **accuracy es engañoso** (un
modelo que siempre predice "no default" ya tiene ~82% accuracy y es inútil).
Usamos **ROC-AUC** y **precision/recall** — lo que de verdad le importa a un
equipo de riesgo: de los que el modelo marca como riesgo alto, ¿cuántos
default'ean de verdad (precision)? ¿Cuántos default reales capturamos
(recall)?
"""},

{"type": "code", "source": r"""
modelos = {
    "Regresión Logística": LogisticRegression(max_iter=1000, class_weight="balanced", random_state=RNG_SEED),
    "Random Forest": RandomForestClassifier(n_estimators=300, max_depth=8, class_weight="balanced",
                                              random_state=RNG_SEED, n_jobs=-1),
}

resultados = {}
for nombre, modelo in modelos.items():
    pipe = Pipeline([("prep", preprocesador), ("modelo", modelo)])
    pipe.fit(X_train, y_train)
    proba_test = pipe.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, proba_test)
    resultados[nombre] = {"pipeline": pipe, "proba": proba_test, "auc": auc}
    print(f"{nombre:<22} ROC-AUC = {auc:.4f}")
"""},

{"type": "code", "source": r"""
mejor_nombre = max(resultados, key=lambda k: resultados[k]["auc"])
mejor = resultados[mejor_nombre]
print(f"Mejor modelo: {mejor_nombre}\n")

y_pred = mejor["pipeline"].predict(X_test)
print(classification_report(y_test, y_pred, target_names=["No default", "Default"]))

cm = confusion_matrix(y_test, y_pred)
print("Matriz de confusión:")
print(pd.DataFrame(cm, index=["Real: No default", "Real: Default"], columns=["Pred: No default", "Pred: Default"]))
"""},

{"type": "markdown", "source": r"""
> **Threshold por defecto (0.5) rara vez es el óptimo de negocio.** Si el costo
> de aprobar un default es mucho mayor que el costo de rechazar a un buen
> pagador, se baja el threshold para ganar recall a costa de precision — y
> viceversa. Se ajusta con la curva precision-recall, no adivinando.
"""},

{"type": "code", "source": r"""
precision, recall, thresholds = precision_recall_curve(y_test, mejor["proba"])

# Ejemplo: threshold que garantiza recall >= 0.75 (capturar al menos 75% de los defaults reales)
idx_validos = np.where(recall[:-1] >= 0.75)[0]
if len(idx_validos) > 0:
    idx_optimo = idx_validos[np.argmax(precision[idx_validos])]  # el de mayor precision entre los válidos
    th_optimo = thresholds[idx_optimo]
    print(f"Threshold para recall>=75%: {th_optimo:.3f} -> precision={precision[idx_optimo]:.3f}, recall={recall[idx_optimo]:.3f}")
    print(f"(vs. threshold default 0.5, que da precision/recall distintos — ver classification_report arriba)")
"""},

{"type": "markdown", "source": r"""
## 4. Validación cruzada y búsqueda de hiperparámetros

Un solo train/test split puede ser optimista o pesimista por azar.
**K-Fold estratificado** promedia el desempeño sobre varios splits. Para
hiperparámetros, `RandomizedSearchCV` explora el espacio de forma más
eficiente que `GridSearchCV` cuando hay muchos parámetros.
"""},

{"type": "code", "source": r"""
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RNG_SEED)
pipe_rf = Pipeline([("prep", preprocesador), ("modelo", RandomForestClassifier(class_weight="balanced", random_state=RNG_SEED, n_jobs=-1))])

scores_cv = cross_val_score(pipe_rf, X_train, y_train, cv=cv, scoring="roc_auc", n_jobs=-1)
print(f"ROC-AUC por fold: {np.round(scores_cv, 3)}")
print(f"Promedio: {scores_cv.mean():.4f}  +/-  {scores_cv.std():.4f}")
"""},

{"type": "code", "source": r"""
espacio_parametros = {
    "modelo__n_estimators": [100, 200, 300, 400],
    "modelo__max_depth": [4, 6, 8, 10, None],
    "modelo__min_samples_leaf": [1, 5, 10, 20],
}

busqueda = RandomizedSearchCV(
    pipe_rf, espacio_parametros, n_iter=12, cv=cv, scoring="roc_auc",
    random_state=RNG_SEED, n_jobs=-1,
)
busqueda.fit(X_train, y_train)

print(f"Mejores hiperparámetros: {busqueda.best_params_}")
print(f"Mejor ROC-AUC (CV): {busqueda.best_score_:.4f}")
print(f"ROC-AUC en test (holdout final): {roc_auc_score(y_test, busqueda.predict_proba(X_test)[:, 1]):.4f}")
"""},

{"type": "markdown", "source": r"""
## 5. Regresión: predecir la tasa de interés

Mismo pipeline, distinto target continuo. Métricas de regresión: **MAE**
(interpretable en las unidades originales), **RMSE** (penaliza más los
errores grandes), **R²** (proporción de varianza explicada — cuidado, no
dice si el modelo es *útil*, solo si explica varianza histórica).
"""},

{"type": "code", "source": r"""
y_reg = df["tasa_interes"]
X_reg = df[features_num + features_cat].copy()
X_reg["buro_score"] = X_reg["buro_score"].fillna(X_reg["buro_score"].median())

Xr_train, Xr_test, yr_train, yr_test = train_test_split(X_reg, y_reg, test_size=0.25, random_state=RNG_SEED)

pipe_reg = Pipeline([("prep", preprocesador), ("modelo", RandomForestRegressor(n_estimators=300, max_depth=8, random_state=RNG_SEED, n_jobs=-1))])
pipe_reg.fit(Xr_train, yr_train)
pred_reg = pipe_reg.predict(Xr_test)

mae = mean_absolute_error(yr_test, pred_reg)
rmse = mean_squared_error(yr_test, pred_reg) ** 0.5
r2 = r2_score(yr_test, pred_reg)

print(f"MAE:  {mae:.4f}  ({mae*100:.2f} puntos porcentuales de tasa)")
print(f"RMSE: {rmse:.4f}")
print(f"R²:   {r2:.4f}")

# Baseline ingenuo: predecir siempre la media -> el modelo DEBE superarlo claramente
baseline_mae = mean_absolute_error(yr_test, np.full_like(yr_test, yr_train.mean()))
print(f"\nBaseline (predecir la media): MAE = {baseline_mae:.4f}")
print(f"Mejora del modelo sobre baseline: {(1 - mae/baseline_mae):.1%}")
"""},

{"type": "markdown", "source": r"""
## 6. Clustering: segmentación de clientes con K-Means

Sin target — el objetivo es encontrar estructura. K-Means requiere elegir
`k` (número de clusters): el **método del codo** (inercia) y el
**silhouette score** son las dos formas estándar de justificarlo, no un
número arbitrario.
"""},

{"type": "code", "source": r"""
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

features_cluster = ["ingreso_mensual", "buro_score", "dti", "monto_solicitado", "antiguedad_empresa_anios"]
X_cluster = df[features_cluster].dropna()
X_cluster_scaled = StandardScaler().fit_transform(X_cluster)

inercias, siluetas = [], []
rango_k = range(2, 9)
for k in rango_k:
    km = KMeans(n_clusters=k, random_state=RNG_SEED, n_init=10)
    labels = km.fit_predict(X_cluster_scaled)
    inercias.append(km.inertia_)
    siluetas.append(silhouette_score(X_cluster_scaled, labels))

for k, inercia, sil in zip(rango_k, inercias, siluetas):
    print(f"k={k}: inercia={inercia:,.0f}, silhouette={sil:.3f}")

k_optimo = rango_k[int(np.argmax(siluetas))]
print(f"\nk óptimo por silhouette: {k_optimo}")
"""},

{"type": "code", "source": r"""
km_final = KMeans(n_clusters=k_optimo, random_state=RNG_SEED, n_init=10)
df_cluster = X_cluster.copy()
df_cluster["cluster"] = km_final.fit_predict(X_cluster_scaled)

perfil_clusters = df_cluster.groupby("cluster").agg(
    n=("ingreso_mensual", "count"),
    ingreso_prom=("ingreso_mensual", "mean"),
    score_prom=("buro_score", "mean"),
    dti_prom=("dti", "mean"),
    monto_prom=("monto_solicitado", "mean"),
).round(1).sort_values("score_prom", ascending=False)

perfil_clusters
"""},

{"type": "markdown", "source": r"""
## 7. Series de tiempo: forecasting

Regla de oro: **siempre compara contra un baseline ingenuo** (último valor
conocido, o media móvil). Un modelo sofisticado que no le gana al baseline no
sirve. Aquí usamos features de calendario + lags con Gradient Boosting, un
enfoque simple y robusto frente a SARIMA clásico cuando hay múltiples
estacionalidades.
"""},

{"type": "code", "source": r"""
precios = pd.read_csv("data/precios_acciones_tech.csv", parse_dates=["fecha"])
serie = precios[precios["ticker"] == "TCH"].set_index("fecha")["precio_cierre"].sort_index()

df_ts = serie.to_frame("precio")
for lag in [1, 2, 3, 5, 10]:
    df_ts[f"lag_{lag}"] = df_ts["precio"].shift(lag)
df_ts["dia_semana"] = df_ts.index.dayofweek
df_ts["media_movil_10"] = df_ts["precio"].shift(1).rolling(10).mean()
df_ts = df_ts.dropna()

# Split TEMPORAL (nunca aleatorio en series de tiempo): últimos 60 días como test
corte = df_ts.index[-60]
train_ts = df_ts[df_ts.index < corte]
test_ts = df_ts[df_ts.index >= corte]

features_ts = [c for c in df_ts.columns if c != "precio"]
modelo_ts = GradientBoostingRegressor(n_estimators=200, max_depth=3, learning_rate=0.05, random_state=RNG_SEED)
modelo_ts.fit(train_ts[features_ts], train_ts["precio"])
pred_ts = modelo_ts.predict(test_ts[features_ts])

# Baseline: "mañana = precio de hoy" (random walk, el baseline estándar en precios financieros)
baseline_ts = test_ts["lag_1"]

mae_modelo = mean_absolute_error(test_ts["precio"], pred_ts)
mae_baseline = mean_absolute_error(test_ts["precio"], baseline_ts)
print(f"MAE modelo (Gradient Boosting):  {mae_modelo:.3f}")
print(f"MAE baseline (random walk):       {mae_baseline:.3f}")
print("-> " + ("El modelo supera al baseline ingenuo." if mae_modelo < mae_baseline else "El baseline ingenuo supera al modelo."))
print("\nEsto es normal y esperado en precios financieros: si un modelo simple le")
print("ganara consistentemente al random walk, sería una señal de arbitraje real.")
print("El valor de este enfoque está en series con estacionalidad/tendencia clara")
print("(ventas, demanda), NO necesariamente en precios de mercado eficientes.")
"""},

{"type": "markdown", "source": r"""
```python
# Alternativa clásica para series con estacionalidad fuerte (ej. ventas mensuales):
from statsmodels.tsa.statespace.sarimax import SARIMAX

modelo_sarima = SARIMAX(
    serie_mensual, order=(1, 1, 1), seasonal_order=(1, 1, 1, 12),
).fit(disp=False)
pronostico = modelo_sarima.get_forecast(steps=6)
intervalo_confianza = pronostico.conf_int()
```
"""},

{"type": "markdown", "source": r"""
## 8. Interpretabilidad: importancia de features

`feature_importances_` de un Random Forest mide reducción de impureza, pero
puede sobre-favorecer variables de alta cardinalidad. **Permutation
importance** es más confiable: mide la caída real en performance al
mezclar aleatoriamente cada feature.
"""},

{"type": "code", "source": r"""
from sklearn.inspection import permutation_importance

pipe_final = busqueda.best_estimator_
resultado_perm = permutation_importance(
    pipe_final, X_test, y_test, n_repeats=10, random_state=RNG_SEED, scoring="roc_auc", n_jobs=-1
)

importancias = pd.Series(resultado_perm.importances_mean, index=X_test.columns).sort_values(ascending=False)
print("Top 8 features por permutation importance (caída de ROC-AUC al mezclarlas):")
print(importancias.head(8).round(4))
"""},

{"type": "markdown", "source": r"""
> Para explicaciones a nivel de **predicción individual** (ej. "¿por qué se
> rechazó esta solicitud específica?"), la herramienta estándar en la
> industria es **SHAP** (`pip install shap`):
> ```python
> import shap
> explainer = shap.TreeExplainer(pipe_final.named_steps["modelo"])
> shap_values = explainer.shap_values(X_test_transformado)
> shap.summary_plot(shap_values, X_test_transformado)
> ```
"""},

{"type": "markdown", "source": r"""
## 9. Checklist anti-leakage

Antes de reportar el desempeño de cualquier modelo:

- [ ] ¿El split respeta la estructura temporal, si existe?
- [ ] ¿Imputación/escalado se ajustan SOLO con train (idealmente vía `Pipeline`)?
- [ ] ¿Alguna feature usa información que no estaría disponible al momento de
      predecir en producción? (ej. usar `default_90d` de OTRA solicitud del
      mismo cliente que ocurrió después)
- [ ] ¿El desempeño se compara contra un baseline simple?
- [ ] ¿La métrica reportada es la que le importa al negocio (no solo la más
      fácil de calcular)?

## Resumen y siguientes pasos

- `Pipeline` + `ColumnTransformer` no es opcional en producción: es la forma
  de garantizar reproducibilidad y evitar leakage por diseño.
- Con clases desbalanceadas, ROC-AUC + precision/recall > accuracy.
- El threshold de decisión es una elección de negocio, no un default de
  sklearn.
- Todo forecast se compara contra un baseline ingenuo — si no le gana, no
  hay caso de negocio.

**Siguiente módulo:** `08_automatizacion_pipelines.ipynb` — llevar esto a
producción: scripts, scheduling, testing y buenas prácticas de ingeniería.
"""},
]
