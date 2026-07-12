CELLS = [
{"type": "markdown", "source": r"""
# 04 · Estadística aplicada para decisiones de negocio

La estadística que usa un analista senior no es "calcular la media" — es
**cuantificar incertidumbre y evitar conclusiones falsas** sobre datos con
ruido. Este módulo cubre las herramientas que realmente se usan para
justificar decisiones frente a stakeholders.

**Dataset:** `credito_solicitudes.csv`.

## Contenido
1. Estadística descriptiva más allá de `.describe()`
2. Distribuciones: por qué importan (y cuándo NO asumir normalidad)
3. Intervalos de confianza (bootstrap y paramétrico)
4. Pruebas de hipótesis: t-test, chi-cuadrado, y el problema de p-hacking
5. Correlación vs. causalidad — con un ejemplo que engaña
6. Tamaño de efecto: por qué "estadísticamente significativo" no es "importante"
"""},

{"type": "code", "source": r"""
import numpy as np
import pandas as pd
from scipy import stats

pd.set_option("display.width", 120)
RNG = np.random.default_rng(7)

df = pd.read_csv("data/credito_solicitudes.csv", parse_dates=["fecha_solicitud"]).dropna(subset=["ingreso_mensual", "buro_score"])
df.shape
"""},

{"type": "markdown", "source": r"""
## 1. Estadística descriptiva más allá de `.describe()`

`.describe()` da media/std/percentiles, pero oculta forma de la distribución.
**Asimetría (skew)** y **curtosis** dicen si "la media" siquiera es un resumen
útil.
"""},

{"type": "code", "source": r"""
ingreso = df["ingreso_mensual"]

resumen = pd.Series({
    "media": ingreso.mean(),
    "mediana": ingreso.median(),
    "desv_estandar": ingreso.std(),
    "asimetria": stats.skew(ingreso),
    "curtosis": stats.kurtosis(ingreso),
    "coef_variacion": ingreso.std() / ingreso.mean(),
}).round(2)
print(resumen)

if abs(resumen["media"] - resumen["mediana"]) / resumen["mediana"] > 0.1:
    print("\n-> Media y mediana difieren >10%: la distribución está sesgada,"
          " la media SOLA es engañosa como resumen (usa mediana o reporta ambas).")
"""},

{"type": "markdown", "source": r"""
## 2. Distribuciones: cuándo NO asumir normalidad

Muchos métodos clásicos (t-test, regresión lineal con inferencia) asumen
normalidad de residuos. `ingreso_mensual` se generó con una lognormal — muy
común en variables de dinero (ingresos, montos, ventas). El test de
Shapiro-Wilk cuantifica el desvío de normalidad en vez de "verlo a ojo" en un
histograma.
"""},

{"type": "code", "source": r"""
muestra = ingreso.sample(min(len(ingreso), 4999), random_state=1)  # Shapiro-Wilk limita tamaño de muestra
stat, p_valor = stats.shapiro(muestra)
print(f"Shapiro-Wilk: estadístico={stat:.4f}, p-valor={p_valor:.2e}")
print("-> Rechazamos normalidad" if p_valor < 0.05 else "-> No hay evidencia contra normalidad")

log_ingreso = np.log(ingreso)
stat_log, p_log = stats.shapiro(log_ingreso.sample(min(len(ingreso), 4999), random_state=1))
print(f"\nLog(ingreso) — Shapiro-Wilk: estadístico={stat_log:.4f}, p-valor={p_log:.2e}")
print("-> log-transform hace la variable mucho más cercana a normal (esperado: es lognormal)")
"""},

{"type": "markdown", "source": r"""
> **Regla práctica:** si una variable de dinero está sesgada a la derecha
> (ingresos, ventas, montos), prueba `np.log1p(x)` antes de correlaciones,
> regresión lineal o modelos que asuman linealidad/normalidad.
"""},

{"type": "markdown", "source": r"""
## 3. Intervalos de confianza: paramétrico vs. bootstrap

El IC paramétrico asume una forma de distribución conocida. El **bootstrap**
(remuestreo con reemplazo) no asume nada sobre la distribución — más robusto,
y hoy es computacionalmente barato.
"""},

{"type": "code", "source": r"""
# IC paramétrico (asume normalidad del estimador vía CLT)
media = ingreso.mean()
error_est = ingreso.std(ddof=1) / np.sqrt(len(ingreso))
ic_parametrico = stats.norm.interval(0.95, loc=media, scale=error_est)

# IC por bootstrap: remuestrear con reemplazo N veces, tomar percentiles 2.5/97.5
def bootstrap_ic(datos, func=np.mean, n_boot=5000, alpha=0.05, rng=RNG):
    datos = np.asarray(datos)
    boot_stats = np.array([
        func(rng.choice(datos, size=len(datos), replace=True))
        for _ in range(n_boot)
    ])
    return np.percentile(boot_stats, [100 * alpha / 2, 100 * (1 - alpha / 2)])

ic_bootstrap = bootstrap_ic(ingreso.to_numpy())

print(f"Media muestral:        ${media:,.0f}")
print(f"IC 95% paramétrico:    (${ic_parametrico[0]:,.0f}, ${ic_parametrico[1]:,.0f})")
print(f"IC 95% bootstrap:      (${ic_bootstrap[0]:,.0f}, ${ic_bootstrap[1]:,.0f})")
print("\nAmbos coinciden bien aquí porque n es grande (CLT aplica). Con muestras")
print("pequeñas o estadísticos no-lineales (mediana, percentiles) el bootstrap es más confiable.")
"""},

{"type": "markdown", "source": r"""
## 4. Pruebas de hipótesis

Caso de negocio real: **¿el score de buró promedio difiere entre solicitudes
que hicieron default y las que no?** (t-test) y **¿la tasa de default depende
del sector?** (chi-cuadrado, variables categóricas).
"""},

{"type": "code", "source": r"""
score_default = df.loc[df["default_90d"] == 1, "buro_score"].dropna()
score_no_default = df.loc[df["default_90d"] == 0, "buro_score"].dropna()

# Levene primero: t-test estándar asume varianzas iguales; si no, usar Welch (equal_var=False)
_, p_levene = stats.levene(score_default, score_no_default)
usar_welch = p_levene < 0.05

t_stat, p_valor = stats.ttest_ind(score_default, score_no_default, equal_var=not usar_welch)

print(f"Levene (igualdad de varianzas): p={p_levene:.4f} -> {'usar Welch t-test' if usar_welch else 'varianzas iguales, t-test estándar OK'}")
print(f"\nScore promedio (default=1):    {score_default.mean():.1f}")
print(f"Score promedio (default=0):    {score_no_default.mean():.1f}")
print(f"t-test: t={t_stat:.2f}, p-valor={p_valor:.2e}")
print("-> Diferencia estadísticamente significativa (p < 0.05)" if p_valor < 0.05 else "-> No significativa")
"""},

{"type": "code", "source": r"""
# Chi-cuadrado: ¿sector y default_90d son independientes?
tabla_contingencia = pd.crosstab(df["sector"], df["default_90d"])
chi2, p_chi, gl, esperado = stats.chi2_contingency(tabla_contingencia)

print(tabla_contingencia)
print(f"\nChi-cuadrado: chi2={chi2:.2f}, gl={gl}, p-valor={p_chi:.4f}")
print("-> Sector y default NO son independientes (asociación significativa)" if p_chi < 0.05
      else "-> No hay evidencia de asociación entre sector y default")
"""},

{"type": "markdown", "source": r"""
> **Sobre p-hacking:** probar 20 variables contra el target "a ver cuál da
> p<0.05" garantiza ~1 falso positivo por azar (con α=0.05). Si haces pruebas
> múltiples, corrige el umbral (ej. **Bonferroni**: α/n_pruebas) o usa
> `statsmodels.stats.multitest.multipletests`.
"""},

{"type": "markdown", "source": r"""
## 5. Correlación vs. causalidad — un ejemplo que engaña

Correlación de Pearson mide relación **lineal**. Dos trampas clásicas:
(1) una tercera variable oculta genera correlación espuria, y
(2) relaciones no-lineales fuertes pueden dar correlación de Pearson ≈ 0.
"""},

{"type": "code", "source": r"""
# Trampa 1: correlación espuria vía variable oculta (antigüedad de empresa)
corr_monto_score = df["monto_solicitado"].corr(df["buro_score"])
print(f"Correlación monto_solicitado vs buro_score: {corr_monto_score:.3f}")

# Controlando por antigüedad de empresa (correlación parcial simple)
from scipy.stats import pearsonr

def correlacion_parcial(x, y, z, data):
    '''Correlación entre x,y controlando linealmente por z (regresión de residuos).'''
    res_x = data[x] - np.polyval(np.polyfit(data[z], data[x], 1), data[z])
    res_y = data[y] - np.polyval(np.polyfit(data[z], data[y], 1), data[z])
    r, p = pearsonr(res_x, res_y)
    return r, p

r_parcial, p_parcial = correlacion_parcial("monto_solicitado", "buro_score", "antiguedad_empresa_anios", df)
print(f"Correlación PARCIAL controlando antigüedad de empresa: {r_parcial:.3f} (p={p_parcial:.4f})")
print("-> Si la correlación parcial baja mucho respecto a la simple, parte del efecto original era espurio.")
"""},

{"type": "code", "source": r"""
# Trampa 2: relación no-lineal con Pearson ~ 0 pero dependencia fuerte y real
x = RNG.uniform(-3, 3, 2000)
y = x**2 + RNG.normal(0, 0.3, 2000)  # relación cuadrática perfecta + ruido

r_pearson, _ = stats.pearsonr(x, y)
r_spearman, _ = stats.spearmanr(x, y)  # captura monotonicidad, no solo linealidad

print(f"Pearson (x, x²+ruido):  {r_pearson:.3f}   <- casi 0, sugiere 'no hay relación' (FALSO)")
print(f"Spearman:                {r_spearman:.3f}   <- también bajo, porque la relación no es monótona")
print("\nConclusión: SIEMPRE grafica (scatter) antes de confiar en un coeficiente de correlación.")
"""},

{"type": "markdown", "source": r"""
## 6. Tamaño de efecto: "significativo" ≠ "importante"

Con `n` grande, hasta diferencias triviales dan p < 0.05. **Cohen's d**
cuantifica qué tan grande es la diferencia en unidades de desviación estándar,
independiente del tamaño de muestra.
"""},

{"type": "code", "source": r"""
def cohens_d(a, b):
    n1, n2 = len(a), len(b)
    var_pooled = ((n1 - 1) * a.var(ddof=1) + (n2 - 1) * b.var(ddof=1)) / (n1 + n2 - 2)
    return (a.mean() - b.mean()) / np.sqrt(var_pooled)

d = cohens_d(score_no_default, score_default)
print(f"Cohen's d (score: no-default vs default): {d:.2f}")

interpretacion = "pequeño" if abs(d) < 0.5 else "mediano" if abs(d) < 0.8 else "grande"
print(f"-> Efecto {interpretacion} (referencia: 0.2=pequeño, 0.5=mediano, 0.8=grande)")
print(f"\np-valor del t-test era {p_valor:.2e} (altamente 'significativo'),")
print(f"pero lo que le importa al negocio es el tamaño de efecto: {interpretacion}.")
"""},

{"type": "markdown", "source": r"""
## Resumen y siguientes pasos

- Reporta mediana + asimetría junto con la media en variables de dinero.
- No asumas normalidad — pruébala (Shapiro) o usa bootstrap, que no la requiere.
- Antes de correlacionar dos variables, pregúntate qué tercera variable podría
  estar generando la relación (o escondiéndola).
- Siempre grafica antes de confiar en un coeficiente de correlación.
- Reporta tamaño de efecto (Cohen's d) junto al p-valor — un resultado puede
  ser significativo y a la vez irrelevante para el negocio.

**Siguiente módulo:** `05_analisis_exploratorio_eda.ipynb` — EDA de punta a
punta sobre datos con nulos, outliers y valores sucios.
"""},
]
