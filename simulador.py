"""
simulador.py - Interfaz del proyecto
"De una carga a un motor: la fuerza de Lorentz simulada y demostrada"

Ejecutar (en la misma carpeta que fisica.py):
    python -m streamlit run simulador.py --theme.base dark
"""
import math

import numpy as np
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import fisica as fx
import animacion

try:
    import streamlit.components.v1 as components
except Exception:  # versiones muy nuevas o muy viejas
    components = None

import inspect

_NUEVO = "width" in inspect.signature(st.plotly_chart).parameters


def mostrar(fig):
    """st.plotly_chart ocupando todo el ancho, sea cual sea la versión de Streamlit."""
    if _NUEVO:
        st.plotly_chart(fig, width="stretch")
    else:
        st.plotly_chart(fig, use_container_width=True)


# ------------------------------------------------------------------ estilo
C_FONDO = "#0B1722"
C_PANEL = "#122434"
C_TEXTO = "#E6EEF5"
C_B = "#4DA3FF"      # campo magnético
C_E = "#FFB347"      # campo eléctrico
C_OK = "#5EE6B0"
C_MAL = "#FF6B6B"

st.set_page_config(page_title="Fuerza de Lorentz", page_icon="⚡", layout="wide")
st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&display=swap');
    .stApp {{ background: radial-gradient(1200px 600px at 15% -10%, #16324a 0%, {C_FONDO} 55%); color: {C_TEXTO}; }}
    [data-testid="stSidebar"] {{ background: {C_PANEL}; }}
    h1, h2, h3 {{ font-family: 'Space Grotesk', sans-serif; letter-spacing: -0.01em; color: {C_TEXTO}; }}
    h1 {{ font-size: 2.1rem; margin-bottom: 0; }}
    p, label, li {{ color: {C_TEXTO}; }}
    [data-testid="stMetric"] {{ background: {C_PANEL}; border-left: 3px solid {C_B}; padding: 10px 14px; border-radius: 6px; }}
    [data-testid="stMetricValue"] {{ font-family: 'Space Grotesk', sans-serif; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------- presets
# clave: (partícula, B mT, Ex, Ey, Ez, v km/s, ángulo con B (°), azimut (°), ciclos, botella)
PRESETS = {
    "Ciclotrón: círculo del electrón": ("Electrón", 1.0, 0, 0, 0, 1000, 90, 0, 5, False),
    "Hélice: velocidad inclinada": ("Electrón", 1.0, 0, 0, 0, 1000, 55, 0, 8, False),
    "Solo campo eléctrico: parábola": ("Electrón", 0.0, 0, 100, 0, 1000, 90, 0, 1, False),
    "Deriva E×B: avanza de lado con lazos": ("Electrón", 1.0, 0, 100, 0, 500, 90, 0, 4, False),
    "Cicloide: parte del reposo": ("Electrón", 1.0, 0, 500, 0, 0, 90, 0, 2, False),
    "Selector de velocidades: va recto si v = E/B": ("Electrón", 1.0, 0, 500, 0, 500, 90, 0, 4, False),
    "Protón: gira al revés y más lento": ("Protón", 100.0, 0, 0, 0, 100, 90, 0, 5, False),
    "Botella magnética: rebota entre extremos": ("Electrón", 1.0, 0, 0, 0, 1000, 60, 0, 25, True),
    "Personalizado": None,
}
CLAVES = ["part", "B", "Ex", "Ey", "Ez", "v", "ang", "azi", "ncyc", "mirror"]


def aplicar_preset():
    p = PRESETS.get(st.session_state["preset"])
    if p is None:
        return
    for k, v in zip(CLAVES, p):
        st.session_state[k] = v


if "init" not in st.session_state:
    st.session_state["preset"] = "Ciclotrón: círculo del electrón"
    aplicar_preset()
    st.session_state.update(
        {"ppc": 100, "metodo": "RK4", "color": "Tiempo", "analitica": True,
         "mV": 1.5, "mRt": 0.5, "mB": 150.0, "mR": 0.8, "mJ": 0.5, "mb": 2.0, "mmed": 0.0,
         "init": True}
    )

# ------------------------------------------------------------------ sidebar
sb = st.sidebar
sb.markdown("### Panel de control")
sb.selectbox("Escenario", list(PRESETS.keys()), key="preset", on_change=aplicar_preset)

sb.markdown("**Partícula**")
sb.selectbox("Tipo", list(fx.PARTICULAS.keys()) + ["Personalizada"], key="part")
if st.session_state["part"] == "Personalizada":
    qe_in = sb.number_input("Carga (múltiplos de e)", -10.0, 10.0, value=1.0, step=1.0)
    mp_in = sb.number_input("Masa (múltiplos de la masa del protón)", 0.0005, 500.0,
                           value=1.0, step=1.0, format="%.4f")
    q_C, m_kg = qe_in * fx.E_CARGA, mp_in * fx.M_PROTON
else:
    qe, m_kg = fx.PARTICULAS[st.session_state["part"]]
    q_C = qe * fx.E_CARGA

sb.markdown("**Campos**")
sb.slider("Campo magnético B (mT, apunta en +z)", 0.0, 500.0, key="B", step=0.05)
sb.slider("Campo eléctrico Ex (V/m)", -5000, 5000, key="Ex", step=10)
sb.slider("Campo eléctrico Ey (V/m)", -5000, 5000, key="Ey", step=10)
sb.slider("Campo eléctrico Ez (V/m)", -5000, 5000, key="Ez", step=10)
sb.checkbox("Botella magnética (B no uniforme)", key="mirror")
if st.session_state["mirror"]:
    L_cm = sb.slider("Longitud característica L (cm)", 1.0, 20.0, value=5.0, step=0.5)

sb.markdown("**Velocidad inicial**")
sb.slider("Rapidez (km/s)", 0, 30000, key="v", step=10)
sb.slider("Ángulo respecto a B (°)", 0, 180, key="ang", step=1)
sb.slider("Dirección en el plano xy (°)", 0, 360, key="azi", step=5)

sb.markdown("**Precisión numérica**")
sb.radio("Método", ["RK4", "Euler"], key="metodo", horizontal=True)
sb.slider("Pasos por vuelta", 20, 400, key="ppc", step=10)
sb.slider("Vueltas simuladas", 1, 60, key="ncyc", step=1)
sb.radio("Color de la trayectoria", ["Tiempo", "Rapidez"], key="color", horizontal=True)
sb.checkbox("Superponer solución analítica", key="analitica")
escala_real = sb.checkbox("Escala real de los ejes (desmárcala para ver el camino más grande)",
                          value=True)
flechas = sb.checkbox("Mostrar flechas de fuerza y velocidad", value=True)
sb.markdown("**Campos en el espacio**")
modo_vec = sb.radio("Vectores de campo (B azul, E naranja)",
                    ["Dinámicos (siguen a la partícula)", "Malla fija", "Ocultos"], index=0)
densidad = sb.slider("Cantidad de vectores y líneas", 2, 7, value=3)
ver_lineas = sb.checkbox("Líneas de campo con flujo animado", value=True)

# ------------------------------------------------------------- simulación
B_T = st.session_state["B"] * 1e-3
E_vec = (float(st.session_state["Ex"]), float(st.session_state["Ey"]), float(st.session_state["Ez"]))
v_ms = st.session_state["v"] * 1e3
ang, azi = math.radians(st.session_state["ang"]), math.radians(st.session_state["azi"])
v0 = (v_ms * math.sin(ang) * math.cos(azi), v_ms * math.sin(ang) * math.sin(azi), v_ms * math.cos(ang))
s0 = np.array([0.0, 0.0, 0.0, *v0])
L_m = L_cm * 1e-2 if (st.session_state["mirror"] and B_T > 0) else None
uniforme = L_m is None


@st.cache_data(show_spinner=False)
def simular(q, m, E, B0, L, v0_, ncyc, ppc, metodo):
    s_ini = np.array([0.0, 0.0, 0.0, *v0_])
    if B0 > 0:
        T = 2 * math.pi / abs(q * B0 / m)
        t_fin, n = ncyc * T, ncyc * ppc
    else:  # sin B: el tiempo que tarda en recorrer ~5 cm
        a = (q / m) * math.sqrt(sum(e * e for e in E))
        v = math.sqrt(sum(c * c for c in v0_))
        d = 0.05
        t_fin = (-v + math.sqrt(v * v + 2 * a * d)) / a if a > 0 else (d / v if v > 0 else 1e-6)
        n = 1000
    return fx.integrar(s_ini, q, m, E, B0, L, t_fin, n, metodo)


t, s = simular(q_C, m_kg, E_vec, B_T, L_m, v0, st.session_state["ncyc"],
               st.session_state["ppc"], st.session_state["metodo"])
# si el método diverge (p. ej. Euler con pocos pasos) se corta la simulación donde se descontrola
ok = np.isfinite(s).all(axis=1) & (np.abs(s).max(axis=1) < 1e9)
truncada = not ok.all()
if truncada:
    k_ok = max(int(np.argmin(ok)), 3)
    t, s = t[:k_ok], s[:k_ok]
ref = fx.analitica(t, q_C, m_kg, E_vec, B_T, s0[:3], s0[3:]) if uniforme else None
th = fx.teoria(q_C, m_kg, E_vec, B_T, v0) if (uniforme and B_T > 0) else None
vmax = float(np.max(np.linalg.norm(s[:, 3:], axis=1)))


def unidad_long(ext):
    for f, u in ((1.0, "m"), (1e-2, "cm"), (1e-3, "mm"), (1e-6, "µm"), (1e-9, "nm")):
        if ext >= f:
            return f, u
    return 1e-9, "nm"


def unidad_t(tt):
    for f, u in ((1.0, "s"), (1e-3, "ms"), (1e-6, "µs"), (1e-9, "ns")):
        if tt >= f:
            return f, u
    return 1e-12, "ps"


@st.cache_data(show_spinner=False)
def comparar_metodos(q, m, E, B0, L, v0_, t_fin, n):
    s_ini = np.array([0.0, 0.0, 0.0, *v0_])
    out = []
    for met in ("Euler", "RK4"):
        tt_, ss_ = fx.integrar(s_ini, q, m, E, B0, L, t_fin, n, met)
        out.append(fx.energia_relativa(tt_, ss_, q, m, E)[0])
    return out


@st.cache_data(show_spinner=False)
def convergencia_cache(q, m, E, B0, v0_):
    return fx.convergencia(q, m, E, B0, np.array([0.0, 0.0, 0.0, *v0_]))


ext = float(max(np.ptp(s[:, 0]), np.ptp(s[:, 1]), np.ptp(s[:, 2]), 1e-12))
fl, ul = unidad_long(ext)
ft, ut = unidad_t(t[-1])

# ------------------------------------------------------------- encabezado
st.markdown("# De una carga a un motor")
st.markdown("**La fuerza de Lorentz simulada y demostrada.** Mueve los controles de la izquierda "
            "y mira cómo cambian el camino de la partícula y los números que lo explican.")
if vmax > 0.1 * fx.C_LUZ:
    st.warning("La partícula supera el 10 % de la velocidad de la luz. Este modelo no incluye "
               "relatividad, así que los resultados dejan de ser fiables.")

if truncada:
    st.warning("Con este método y estos pasos la simulación se descontrola y se detuvo antes de "
               "terminar. Aumenta los pasos por vuelta o cambia a RK4.")

c1, c2, c3, c4 = st.columns(4)
if th:
    c1.metric("Radio de giro", f"{th['r'] / fl:.3g} {ul}")
    c2.metric("Periodo de giro", f"{th['T'] / ft:.3g} {ut}")
    c3.metric("Frecuencia de ciclotrón", f"{th['f'] / 1e6:.3g} MHz")
    c4.metric("Deriva E×B", f"{th['deriva'] / 1e3:.3g} km/s")
else:
    a_teo = q_C / m_kg * math.sqrt(sum(e * e for e in E_vec))
    c1.metric("Aceleración", f"{a_teo:.3g} m/s²")
    c2.metric("Rapidez máxima", f"{vmax / 1e3:.4g} km/s")
    c3.metric("Duración simulada", f"{t[-1] / ft:.3g} {ut}")
    c4.metric("Campo B", "no uniforme" if L_m else "apagado")

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Simulador 3D", "Vistas y energía", "Validación", "Motor homopolar", "Teoría"])


def layout_oscuro(fig, titulo=None, h=520, top=None):
    """Estilo común. `top` deja espacio arriba para los títulos de los subgráficos."""
    fig.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=C_TEXTO), height=h,
        margin=dict(l=10, r=10, t=top if top else (40 if titulo else 10), b=10),
        title=titulo,
    )
    fig.update_xaxes(automargin=True)
    fig.update_yaxes(automargin=True)
    fig.update_annotations(font=dict(size=15, color=C_TEXTO, family="Space Grotesk, sans-serif"))
    return fig


# ================================================================= TAB 1
def flecha3d(p, d, L):
    """Segmentos de una flecha 3D que sale de p con la dirección de d y longitud L.
    Devuelve (xs, ys, zs) con None para cortar la línea entre el cuerpo y la punta."""
    n = float(np.linalg.norm(d))
    if not (n > 0 and L > 0):
        return [None], [None], [None]
    u = np.asarray(d, dtype=float) / n
    punta = p + u * L
    h = 0.28 * L
    ayuda = np.array([0.0, 0.0, 1.0]) if abs(u[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    w = np.cross(u, ayuda)
    w /= np.linalg.norm(w)
    base = punta - u * h
    pts = [p, punta, base + w * 0.45 * h, None, punta, base - w * 0.45 * h]
    return ([None if q is None else float(q[0]) for q in pts],
            [None if q is None else float(q[1]) for q in pts],
            [None if q is None else float(q[2]) for q in pts])


def flecha2d(p, d, L):
    """Igual que flecha3d pero proyectada en el plano x–y."""
    n = float(np.hypot(d[0], d[1]))
    if not (n > 0 and L > 0):
        return [None], [None]
    u = np.array([d[0] / n, d[1] / n])
    w = np.array([-u[1], u[0]])
    punta = np.asarray(p, dtype=float) + u * L
    h = 0.28 * L
    base = punta - u * h
    pts = [np.asarray(p, dtype=float), punta, base + w * 0.45 * h, None, punta, base - w * 0.45 * h]
    return ([None if q is None else float(q[0]) for q in pts],
            [None if q is None else float(q[1]) for q in pts])


def mostrar_animado(fig, nombres, alto, paso_ms=40, div_id="grafico", rotar=False):
    """Figura animada con reproductor propio (ocupa todo el ancho y tiene pantalla completa)."""
    if components is not None:
        try:
            components.html(animacion.construir_html(fig, nombres, paso_ms, div_id, rotar),
                            height=int(alto), scrolling=False)
            return
        except Exception:
            pass
    mostrar(fig)  # plan B: gráfico sin barra de animación


def flechas_varias_3d(P, V, L):
    """UNA sola traza con muchas flechas 3D: P (n,3) puntos, V (n,3) direcciones, L (n,) largos."""
    xs, ys, zs = [], [], []
    for p, d, l in zip(P, V, L):
        ax_, ay_, az_ = flecha3d(np.asarray(p, float), d, l)
        if ax_ == [None]:
            continue
        xs += ax_ + [None]; ys += ay_ + [None]; zs += az_ + [None]
    return xs, ys, zs


def flechas_varias_2d(P, V, L):
    xs, ys = [], []
    for p, d, l in zip(P, V, L):
        ax_, ay_ = flecha2d(np.asarray(p, float), d, l)
        if ax_ == [None]:
            continue
        xs += ax_ + [None]; ys += ay_ + [None]
    return xs, ys


@st.cache_data(show_spinner=False)
def lineas_de_campo(lo, hi, n, E, B0, L):
    """Líneas de campo B y E dentro de la caja [lo, hi] (SI). Devuelve dos listas de polilíneas."""
    lo, hi = np.array(lo), np.array(hi)
    centro, lado = (lo + hi) / 2, float((hi - lo).max())
    paso = lado / 70.0
    n_l = max(2, min(int(n), 5))
    lineas_B, lineas_E = [], []
    if B0 > 0:
        xs_ = np.linspace(lo[0] + 0.2 * (hi[0] - lo[0]), hi[0] - 0.2 * (hi[0] - lo[0]), n_l)
        ys_ = np.linspace(lo[1] + 0.2 * (hi[1] - lo[1]), hi[1] - 0.2 * (hi[1] - lo[1]), n_l)
        for x0 in xs_:
            for y0 in ys_:
                lineas_B.append(fx.linea_de_campo(
                    [x0, y0, centro[2]], lambda p: fx.campo_B_vec(p, B0, L)[0], lo, hi, paso, 160))
    emod = float(np.linalg.norm(E))
    if emod > 0:
        u = np.array(E) / emod
        ayuda = np.array([0.0, 0.0, 1.0]) if abs(u[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
        w1 = np.cross(u, ayuda); w1 /= np.linalg.norm(w1)
        w2 = np.cross(u, w1)
        for a in np.linspace(-0.3, 0.3, min(n_l, 4)):
            for b_ in np.linspace(-0.3, 0.3, min(n_l, 4)):
                lineas_E.append(fx.linea_de_campo(
                    centro + a * lado * w1 + b_ * lado * w2, lambda p: np.array(E, float),
                    lo, hi, paso, 160))
    return lineas_B, lineas_E


def traza_lineas_3d(lineas, fl, color, nombre):
    xs, ys, zs = [], [], []
    for ln in lineas:
        if len(ln) < 2:
            continue
        xs += list(ln[:, 0] / fl) + [None]; ys += list(ln[:, 1] / fl) + [None]
        zs += list(ln[:, 2] / fl) + [None]
    return go.Scatter3d(x=xs or [None], y=ys or [None], z=zs or [None], mode="lines", name=nombre,
                        line=dict(color=color, width=2), hoverinfo="skip", opacity=0.35)


NOM_F = ["Fuerza eléctrica (qE)", "Fuerza magnética (q v×B)", "Velocidad (v)"]
COL_F = [C_E, C_B, "#FFFFFF"]
ANCHO_F = [8, 8, 5]


with tab1:
    X, Y, Z = s[:, 0] / fl, s[:, 1] / fl, s[:, 2] / fl
    rap = np.linalg.norm(s[:, 3:], axis=1)
    if st.session_state["color"] == "Tiempo":
        cvals, cbar = t / ft, f"t ({ut})"
    else:
        cvals, cbar = rap / 1e3, "rapidez (km/s)"
    cmin, cmax = float(np.nanmin(cvals)), float(np.nanmax(cvals))
    n_pts = len(t)
    paso_d = max(1, n_pts // 900)
    idx = np.arange(0, n_pts, paso_d)
    if idx[-1] != n_pts - 1:
        idx = np.append(idx, n_pts - 1)
    n_fr = min(70, len(idx))
    fr_idx = np.linspace(1, len(idx), n_fr).astype(int)
    nombres = [str(k) for k in fr_idx]

    col_v, col_h = st.columns([3, 2])
    vista = col_v.radio("Vista", ["3D", "Plano x–y (desde arriba)"], horizontal=True, key="vista")
    alto = col_h.slider("Altura del gráfico (px)", 480, 1000, 720, step=20)

    # fuerzas en cada punto: qE, q v×B y la velocidad (para las flechas)
    FE_all, FB_all = fx.fuerzas(s, q_C, E_vec, B_T, L_m)
    vel_all = s[:, 3:6]
    F_top = float(max(np.nanmax(np.linalg.norm(FE_all, axis=1)),
                      np.nanmax(np.linalg.norm(FB_all, axis=1))))
    v_top = float(np.nanmax(np.linalg.norm(vel_all, axis=1)))
    LONG_F = [0.22, 0.22, 0.16]   # longitud máxima de cada flecha respecto al lado del cuadro

    def datos_flechas(j, lado, plano):
        out = []
        for vec, tope, fr in ((FE_all[j], F_top, LONG_F[0]), (FB_all[j], F_top, LONG_F[1]),
                              (vel_all[j], v_top, LONG_F[2])):
            if plano:
                mag = float(np.hypot(vec[0], vec[1]))
                L = lado * fr * mag / tope if tope > 0 else 0.0
                out.append(flecha2d((X[j], Y[j]), vec, L))
            else:
                mag = float(np.linalg.norm(vec))
                L = lado * fr * mag / tope if tope > 0 else 0.0
                out.append(flecha3d(np.array([X[j], Y[j], Z[j]]), vec, L))
        return out

    emod_ = math.sqrt(sum(e * e for e in E_vec))
    trazas_vivas = [0, 1] + ([2, 3, 4] if flechas else [])

    if vista == "3D":
        # Cuadro con rangos EXPLÍCITOS en los tres ejes: si la trayectoria es plana (z = 0)
        # un eje de grosor cero haría desaparecer la curva.
        lo = np.array([np.nanmin(X), np.nanmin(Y), np.nanmin(Z)])
        hi = np.array([np.nanmax(X), np.nanmax(Y), np.nanmax(Z)])
        centro = (lo + hi) / 2
        span = float(max((hi - lo).max(), 1e-9))
        spans = np.full(3, span) if escala_real else np.maximum(hi - lo, span * 0.05)
        rangos = [[float(c - 0.6 * sp), float(c + 0.6 * sp)] for c, sp in zip(centro, spans)]
        lado = rangos[0][1] - rangos[0][0]
        anch = np.array([rg[1] - rg[0] for rg in rangos])
        cen = np.array([(rg[0] + rg[1]) / 2 for rg in rangos])
        lo_g, hi_g = (cen - 0.35 * anch) * fl, (cen + 0.35 * anch) * fl      # caja de las líneas (SI)

        fig = go.Figure()
        vivas = [0, 1] + ([2, 3, 4] if flechas else [])       # trazas que cambian en la animación
        contador = [len(vivas)]
        dinamicas = []                                         # funciones (j, k) -> traza del cuadro

        def nueva(traza, viva=None):
            """Agrega una traza; si es dinámica guarda cómo recalcularla en cada cuadro."""
            fig.add_trace(traza)
            if viva is not None:
                vivas.append(contador[0]); dinamicas.append(viva)
            contador[0] += 1

        fig.add_trace(go.Scatter3d(
            x=X[idx], y=Y[idx], z=Z[idx], mode="lines", name="trayectoria",
            line=dict(color=cvals[idx], colorscale="Turbo", width=7, cmin=cmin, cmax=cmax,
                      colorbar=dict(title=cbar, thickness=12, len=0.6, x=1.0)),
            hoverinfo="skip"))
        fig.add_trace(go.Scatter3d(
            x=[X[0]], y=[Y[0]], z=[Z[0]], mode="markers", name="partícula",
            marker=dict(size=9, color="white", line=dict(color=C_E, width=3))))
        if flechas:
            for (xs, ys, zs), nm, col, wd in zip(datos_flechas(0, lado, False), NOM_F, COL_F, ANCHO_F):
                fig.add_trace(go.Scatter3d(x=xs, y=ys, z=zs, mode="lines", name=nm,
                                           line=dict(color=col, width=wd), hoverinfo="skip"))

        # --- vectores de campo DINÁMICOS: una pequeña malla que viaja con la partícula
        emod = math.sqrt(sum(e * e for e in E_vec))
        if modo_vec.startswith("Din"):
            n_loc = 2 if densidad <= 3 else (3 if densidad <= 5 else 4)
            sep_loc = lado * (0.20 if n_loc == 2 else 0.12)
            ejes_loc = (np.arange(n_loc) - (n_loc - 1) / 2) * sep_loc
            OFF = np.array(np.meshgrid(ejes_loc, ejes_loc, ejes_loc, indexing="ij")).reshape(3, -1).T
            B_ref = float(np.max(np.linalg.norm(fx.campo_B_vec(s[:, :3], B_T, L_m), axis=1))) or 1.0

            def vec_local(campo, ref_mag, color, mov, nombre):
                def calcular(j, k=0):
                    pts_si = s[j, :3] + (OFF + mov * sep_loc) * fl
                    V = campo(pts_si)
                    mag = np.linalg.norm(V, axis=1)
                    L = 0.85 * sep_loc * np.minimum(mag / ref_mag, 1.3)
                    xs, ys, zs = flechas_varias_3d(pts_si / fl, V, L)
                    return go.Scatter3d(x=xs or [None], y=ys or [None], z=zs or [None], mode="lines",
                                        name=nombre, line=dict(color=color, width=4), opacity=0.9,
                                        hoverinfo="skip")
                return calcular
            if B_T > 0:
                f_b = vec_local(lambda P_: fx.campo_B_vec(P_, B_T, L_m), B_ref, C_B, 0.0, "Vectores de B")
                nueva(f_b(idx[0]), f_b)
            if emod > 0:
                f_e = vec_local(lambda P_: fx.campo_E(P_, E_vec), emod, C_E, 0.5, "Vectores de E")
                nueva(f_e(idx[0]), f_e)

        # --- líneas de campo (finas y translúcidas) con puntos que fluyen por ellas
        lB = lE = []
        if ver_lineas:
            lB, lE = lineas_de_campo(tuple(lo_g), tuple(hi_g), int(densidad), E_vec, B_T, L_m)

            def flujo(lineas, color, nombre):
                info = []
                for ln in lineas:
                    if len(ln) < 2:
                        continue
                    cum = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(ln, axis=0), axis=1))])
                    info.append((ln, cum, cum[-1]))

                def calcular(j, k=0):
                    fase = k / max(n_fr, 1) * 1.5
                    pts = []
                    for ln, cum, Lt in info:
                        for m_ in range(3):
                            d = ((m_ / 3.0 + fase) % 1.0) * Lt
                            pts.append([np.interp(d, cum, ln[:, c]) for c in range(3)])
                    P_ = np.array(pts).reshape(-1, 3) / fl
                    return go.Scatter3d(x=P_[:, 0] if len(P_) else [None], y=P_[:, 1] if len(P_) else [None],
                                        z=P_[:, 2] if len(P_) else [None], mode="markers", name=nombre,
                                        marker=dict(size=5, color=color, opacity=0.95), hoverinfo="skip")
                return calcular
            if lB:
                f_fb = flujo(lB, C_B, "Flujo de B"); nueva(f_fb(idx[0], 0), f_fb)
            if lE:
                f_fe = flujo(lE, C_E, "Flujo de E"); nueva(f_fe(idx[0], 0), f_fe)
            if lB:
                nueva(traza_lineas_3d(lB, fl, C_B, "Líneas de B"))
            if lE:
                nueva(traza_lineas_3d(lE, fl, C_E, "Líneas de E"))

        # --- malla fija de vectores (opcional)
        if modo_vec == "Malla fija":
            n_v = int(densidad)
            Gp, Ev_, Bv_ = fx.malla_campos(lo_g, hi_g, n_v, E_vec, B_T, L_m)
            sep = float(np.min(0.7 * anch / max(n_v - 1, 1)))
            Pplot = Gp / fl
            if B_T > 0:
                mb = np.linalg.norm(Bv_, axis=1)
                xs, ys, zs = flechas_varias_3d(Pplot, Bv_, 0.8 * sep * mb / mb.max())
                nueva(go.Scatter3d(x=xs or [None], y=ys or [None], z=zs or [None], mode="lines",
                                   name="Vectores de B", line=dict(color=C_B, width=3), opacity=0.8,
                                   hoverinfo="skip"))
            if emod > 0:
                desp = np.array([0.3 * sep, 0.3 * sep, 0.0])
                xs, ys, zs = flechas_varias_3d(Pplot + desp, Ev_, np.full(len(Ev_), 0.8 * sep))
                nueva(go.Scatter3d(x=xs or [None], y=ys or [None], z=zs or [None], mode="lines",
                                   name="Vectores de E", line=dict(color=C_E, width=3), opacity=0.8,
                                   hoverinfo="skip"))

        if ref is not None and st.session_state["analitica"]:
            nueva(go.Scatter3d(
                x=ref[idx, 0] / fl, y=ref[idx, 1] / fl, z=ref[idx, 2] / fl, mode="lines",
                name="solución analítica", line=dict(color="white", width=2, dash="dash")))
        nueva(go.Scatter3d(
            x=[X[0]], y=[Y[0]], z=[Z[0]], mode="markers", name="inicio",
            marker=dict(size=5, color=C_OK, symbol="diamond")))

        # indicadores de campo en la esquina SOLO si no se muestra ningún otro dibujo de campo
        if modo_vec == "Ocultos" and not ver_lineas:
            tam = lado * 0.14
            if B_T > 0:
                nueva(go.Cone(
                    x=[rangos[0][0]], y=[rangos[1][0]], z=[rangos[2][0]], u=[0], v=[0], w=[1],
                    sizemode="absolute", sizeref=tam, anchor="tail", showscale=False,
                    colorscale=[[0, C_B], [1, C_B]], name="Campo B", showlegend=True, hoverinfo="name"))
            if emod > 0:
                nueva(go.Cone(
                    x=[rangos[0][1]], y=[rangos[1][0]], z=[rangos[2][0]],
                    u=[E_vec[0] / emod], v=[E_vec[1] / emod], w=[E_vec[2] / emod],
                    sizemode="absolute", sizeref=tam, anchor="tail", showscale=False,
                    colorscale=[[0, C_E], [1, C_E]], name="Campo E", showlegend=True, hoverinfo="name"))

        frames = []
        for kk, k in enumerate(fr_idx):
            j = idx[k - 1]
            datos = [go.Scatter3d(x=X[idx[:k]], y=Y[idx[:k]], z=Z[idx[:k]], mode="lines",
                                  line=dict(color=cvals[idx[:k]], colorscale="Turbo", width=7,
                                            cmin=cmin, cmax=cmax), hoverinfo="skip"),
                     go.Scatter3d(x=[X[j]], y=[Y[j]], z=[Z[j]], mode="markers",
                                  marker=dict(size=9, color="white", line=dict(color=C_E, width=3)))]
            if flechas:
                for (xs, ys, zs), col, wd in zip(datos_flechas(j, lado, False), COL_F, ANCHO_F):
                    datos.append(go.Scatter3d(x=xs, y=ys, z=zs, mode="lines",
                                              line=dict(color=col, width=wd), hoverinfo="skip"))
            for calcular in dinamicas:
                datos.append(calcular(j, kk))
            frames.append(go.Frame(name=str(k), data=datos, traces=list(vivas)))
        fig.frames = frames
        eje = dict(gridcolor="#1c3a52", showbackground=False, zeroline=False, autorange=False)
        fig.update_layout(
            scene=dict(
                xaxis=dict(title=f"x ({ul})", range=rangos[0], **eje),
                yaxis=dict(title=f"y ({ul})", range=rangos[1], **eje),
                zaxis=dict(title=f"z ({ul})", range=rangos[2], **eje),
                aspectmode="cube", bgcolor="rgba(0,0,0,0)",
                camera=dict(eye=dict(x=1.5, y=-1.5, z=1.0))),
            legend=dict(orientation="h", y=1.0, yanchor="bottom", x=0.0))
        layout_oscuro(fig, h=None, top=60)
        mostrar_animado(fig, nombres, alto, 40, "viz3d", rotar=True)
        st.caption("Flechas: naranja = fuerza eléctrica qE · azul = fuerza magnética q v×B · blanca = "
                   "velocidad. Los vectores de campo (azul = B, naranja = E) viajan con la partícula y "
                   "los puntos fluyen por las líneas de campo. Pulsa ▶ y prueba ⟳ Girar vista; "
                   "⛶ abre la pantalla completa.")
    else:
        lado = float(max(np.nanmax(X) - np.nanmin(X), np.nanmax(Y) - np.nanmin(Y), 1e-9)) * 1.2
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=X[idx], y=Y[idx], mode="markers", name="trayectoria",
            marker=dict(size=5, color=cvals[idx], colorscale="Turbo", cmin=cmin, cmax=cmax,
                        colorbar=dict(title=cbar, thickness=12, len=0.7))))
        fig.add_trace(go.Scatter(
            x=[X[0]], y=[Y[0]], mode="markers", name="partícula",
            marker=dict(size=13, color="white", line=dict(color=C_E, width=3))))
        if flechas:
            for (xs, ys), nm, col, wd in zip(datos_flechas(0, lado, True), NOM_F, COL_F, ANCHO_F):
                fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", name=nm,
                                         line=dict(color=col, width=wd - 2), hoverinfo="skip"))
        if ref is not None and st.session_state["analitica"]:
            fig.add_trace(go.Scatter(x=ref[idx, 0] / fl, y=ref[idx, 1] / fl, mode="lines",
                                     name="solución analítica",
                                     line=dict(color="white", width=1.5, dash="dash")))
        if modo_vec != "Ocultos":
            n_v = int(densidad)
            cx_, cy_ = (np.nanmax(X) + np.nanmin(X)) / 2, (np.nanmax(Y) + np.nanmin(Y)) / 2
            gx = np.linspace(cx_ - 0.6 * lado, cx_ + 0.6 * lado, n_v)
            gy = np.linspace(cy_ - 0.6 * lado, cy_ + 0.6 * lado, n_v)
            GX, GY = np.meshgrid(gx, gy, indexing="ij")
            Pg = np.column_stack([GX.ravel(), GY.ravel(), np.full(GX.size, (np.nanmax(Z) + np.nanmin(Z)) / 2)])
            sep = 1.2 * lado / max(n_v - 1, 1)
            campos = []
            if B_T > 0:
                campos.append((fx.campo_B_vec(Pg * fl, B_T, L_m), C_B, "B"))
            if emod_ > 0:
                campos.append((fx.campo_E(Pg, E_vec), C_E, "E"))
            for V, col, nom in campos:
                dentro = np.hypot(V[:, 0], V[:, 1]) < 0.25 * np.linalg.norm(V, axis=1)   # sale o entra de la hoja
                if dentro.any():
                    fig.add_trace(go.Scatter(
                        x=Pg[dentro, 0], y=Pg[dentro, 1], mode="markers", name=f"{nom} ⊙ sale · ⊗ entra",
                        marker=dict(size=13, color=col, symbol=["circle-dot" if v > 0 else "x" for v in V[dentro, 2]],
                                    line=dict(color=col, width=2), opacity=0.8), hoverinfo="skip"))
                fuera = ~dentro
                if fuera.any():
                    mag = np.hypot(V[fuera, 0], V[fuera, 1])
                    xs, ys = flechas_varias_2d(Pg[fuera, :2], V[fuera, :2], 0.7 * sep * mag / mag.max())
                    fig.add_trace(go.Scatter(x=xs or [None], y=ys or [None], mode="lines", name=f"Vectores de {nom}",
                                             line=dict(color=col, width=3), hoverinfo="skip"))
        frames = []
        for k in fr_idx:
            j = idx[k - 1]
            datos = [go.Scatter(x=X[idx[:k]], y=Y[idx[:k]], mode="markers",
                                marker=dict(size=5, color=cvals[idx[:k]], colorscale="Turbo",
                                            cmin=cmin, cmax=cmax)),
                     go.Scatter(x=[X[j]], y=[Y[j]], mode="markers",
                                marker=dict(size=13, color="white", line=dict(color=C_E, width=3)))]
            if flechas:
                for (xs, ys), col, wd in zip(datos_flechas(j, lado, True), COL_F, ANCHO_F):
                    datos.append(go.Scatter(x=xs, y=ys, mode="lines",
                                            line=dict(color=col, width=wd - 2), hoverinfo="skip"))
            frames.append(go.Frame(name=str(k), data=datos, traces=trazas_vivas))
        fig.frames = frames
        fig.update_xaxes(title_text=f"x ({ul})", gridcolor="#25405a")
        fig.update_yaxes(title_text=f"y ({ul})", gridcolor="#25405a", scaleanchor="x")
        fig.update_layout(legend=dict(orientation="h", y=1.0, yanchor="bottom", x=0.0))
        layout_oscuro(fig, h=None, top=60)
        mostrar_animado(fig, nombres, alto, 40, "viz2d")
        st.caption("Vista desde arriba (plano x–y) con los dos ejes a la misma escala. Las flechas "
                   "muestran solo la parte que está en este plano. ⛶ abre la pantalla completa.")

# ================================================================= TAB 2
with tab2:
    er, K = fx.energia_relativa(t, s, q_C, m_kg, E_vec)
    fig2 = make_subplots(rows=1, cols=3, subplot_titles=("Vista x–y", "Vista x–z", "Vista y–z"))
    pares = [(X, Y, "x", "y"), (X, Z, "x", "z"), (Y, Z, "y", "z")]
    for c, (a, b_, na, nb) in enumerate(pares, start=1):
        fig2.add_trace(go.Scatter(x=a, y=b_, mode="lines", line=dict(color=C_B, width=2),
                                  showlegend=False), row=1, col=c)
        fig2.add_trace(go.Scatter(x=[a[0]], y=[b_[0]], mode="markers",
                                  marker=dict(color=C_OK, size=8), showlegend=False), row=1, col=c)
        fig2.update_xaxes(title_text=f"{na} ({ul})", row=1, col=c)
        fig2.update_yaxes(title_text=f"{nb} ({ul})", scaleanchor=f"x{'' if c == 1 else c}",
                          row=1, col=c)
    layout_oscuro(fig2, h=400, top=70)
    mostrar(fig2)

    fig3 = make_subplots(rows=1, cols=2, subplot_titles=("Velocidad en el tiempo",
                                                          "Conservación de la energía"))
    for k, (nombre, col) in enumerate((("vx", C_B), ("vy", C_E), ("vz", C_OK))):
        fig3.add_trace(go.Scatter(x=t / ft, y=s[:, 3 + k] / 1e3, name=nombre,
                                  line=dict(color=col, width=2)), row=1, col=1)
    fig3.update_xaxes(title_text=f"t ({ut})", row=1, col=1)
    fig3.update_yaxes(title_text="km/s", row=1, col=1)

    # comparación de métodos con el mismo número de pasos
    n_pasos = len(t) - 1
    er_e, er_r = comparar_metodos(q_C, m_kg, E_vec, B_T, L_m, v0, float(t[-1]), n_pasos)
    piso = 1e-17
    fig3.add_trace(go.Scatter(x=t / ft, y=np.maximum(np.abs(er_e), piso), name="Euler",
                              line=dict(color=C_MAL, width=2)), row=1, col=2)
    fig3.add_trace(go.Scatter(x=t / ft, y=np.maximum(np.abs(er_r), piso), name="RK4",
                              line=dict(color=C_OK, width=2)), row=1, col=2)
    fig3.update_yaxes(type="log", title_text="|ΔE| / E", row=1, col=2)
    fig3.update_xaxes(title_text=f"t ({ut})", row=1, col=2)
    layout_oscuro(fig3, h=400, top=70)
    mostrar(fig3)
    # campos E y B en la posición de la partícula (calculados con fisica.campo_B_vec / campo_E)
    B_trayecto = np.linalg.norm(fx.campo_B_vec(s[:, :3], B_T, L_m), axis=1) * 1e3
    E_trayecto = np.linalg.norm(fx.campo_E(s[:, :3], E_vec), axis=1)
    fig_c = make_subplots(rows=1, cols=2, subplot_titles=("Campo magnético |B| que siente la partícula",
                                                           "Campo eléctrico |E| que siente la partícula"))
    fig_c.add_trace(go.Scatter(x=t / ft, y=B_trayecto, line=dict(color=C_B, width=3), showlegend=False), row=1, col=1)
    fig_c.add_trace(go.Scatter(x=t / ft, y=E_trayecto, line=dict(color=C_E, width=3), showlegend=False), row=1, col=2)
    fig_c.update_xaxes(title_text=f"t ({ut})")
    fig_c.update_yaxes(title_text="mT", row=1, col=1, rangemode="tozero")
    fig_c.update_yaxes(title_text="V/m", row=1, col=2, rangemode="tozero")
    layout_oscuro(fig_c, h=360, top=70)
    mostrar(fig_c)
    st.caption("Con B uniforme el valor es constante; en la botella magnética crece hacia los extremos, "
               "donde la partícula se refleja.")

    with st.expander("Calcular el campo eléctrico y el magnético en un punto"):
        cA, cB_, cC = st.columns(3)
        px = cA.number_input("x (mm)", value=0.0, step=1.0)
        py = cB_.number_input("y (mm)", value=0.0, step=1.0)
        pz = cC.number_input("z (mm)", value=0.0, step=1.0)
        P_ = np.array([[px, py, pz]]) * 1e-3
        Bp = fx.campo_B_vec(P_, B_T, L_m)[0]
        Ep = fx.campo_E(P_, E_vec)[0]
        st.markdown(
            "| Campo | x | y | z | Magnitud |\n|---|---|---|---|---|\n"
            f"| **B** (mT) | {Bp[0] * 1e3:.4g} | {Bp[1] * 1e3:.4g} | {Bp[2] * 1e3:.4g} | {np.linalg.norm(Bp) * 1e3:.4g} |\n"
            f"| **E** (V/m) | {Ep[0]:.4g} | {Ep[1]:.4g} | {Ep[2]:.4g} | {np.linalg.norm(Ep):.4g} |")
        st.caption("B y E se calculan con las mismas funciones que usa la simulación (fisica.campo_B_vec y "
                   "fisica.campo_E).")

    st.caption("El campo magnético no hace trabajo, así que la energía total debe mantenerse "
               "constante. Con los mismos pasos, RK4 la conserva mucho mejor que Euler, que va "
               "ganando energía y hace que la partícula se aleje en espiral.")

# ================================================================= TAB 3
with tab3:
    if not uniforme or B_T <= 0:
        st.info("La validación analítica se hace con B uniforme mayor que 0. Desactiva la botella "
                "magnética y sube B para ver esta pestaña.")
    elif truncada:
        st.info("La simulación se detuvo porque el método diverge, así que no hay datos completos "
                "para validar. Aumenta los pasos por vuelta o usa RK4.")
    else:
        ncyc = st.session_state["ncyc"]
        me = fx.medir(t, s, ncyc)
        filas = [("Radio de giro (mm)", th["r"] * 1e3, me["r"] * 1e3),
                 ("Periodo (ns)", th["T"] * 1e9, me["T"] * 1e9),
                 ("Velocidad de deriva (km/s)", th["deriva"] / 1e3, me["deriva"] / 1e3)]
        if th["paso"] is not None:
            filas.append(("Paso de la hélice (mm)", th["paso"] * 1e3, me["paso"] * 1e3))

        st.markdown("#### Teoría frente a simulación")
        st.caption("Las columnas de simulación se miden solo con los datos numéricos de RK4/Euler, "
                   "sin usar las fórmulas.")
        encabezado = "| Magnitud | Teoría | Simulación | Error relativo |\n|---|---|---|---|\n"
        cuerpo = ""
        for nombre, a, b_ in filas:
            if abs(a) > 1e-12 and not math.isnan(b_):
                e_rel = f"{abs(b_ - a) / abs(a) * 100:.2e} %"
            else:
                e_rel = "–"
            cuerpo += f"| {nombre} | {a:.6g} | {b_:.6g} | {e_rel} |\n"
        st.markdown(encabezado + cuerpo)

        err_pos = np.max(np.linalg.norm(s[:, :3] - ref[:, :3], axis=1))
        escala = max(th["r"], 1e-12)
        st.metric("Máxima diferencia de posición con la solución exacta",
                  f"{err_pos / fl:.3g} {ul}", f"{err_pos / escala * 100:.2e} % del radio",
                  delta_color="off")

        st.markdown("#### ¿Qué tan bien converge el método?")
        with st.spinner("Calculando la convergencia…"):
            conv = convergencia_cache(q_C, m_kg, E_vec, B_T, v0)
        fig4 = go.Figure()
        for nombre, col in (("Euler", C_MAL), ("RK4", C_OK)):
            d = conv[nombre]
            fig4.add_trace(go.Scatter(x=d["dt"], y=d["err"], mode="lines+markers",
                                      name=f"{nombre} (pendiente ≈ {d['pendiente']:.2f})",
                                      line=dict(color=col, width=2)))
        fig4.update_xaxes(type="log", title_text="paso de tiempo dt (s)")
        fig4.update_yaxes(type="log", title_text="error máximo de posición (m)")
        layout_oscuro(fig4, h=420)
        mostrar(fig4)
        st.caption("En escala log-log la pendiente es el orden del método: al reducir el paso a la "
                   "mitad, el error de RK4 baja unas 16 veces y el de Euler solo 2.")

# ================================================================= TAB 4
with tab4:
    st.markdown("#### Del electrón suelto al motor de cobre")
    st.markdown(
        "Un alambre con corriente en un campo magnético recibe fuerza porque cada electrón "
        "siente la misma fuerza de Lorentz que simulaste. En el motor homopolar, la corriente "
        "va del centro al borde y el imán la empuja de lado, de modo que el conjunto gira.")
    m1, m2 = st.columns([1, 2])
    with m1:
        st.slider("Voltaje de la pila (V)", 0.5, 12.0, key="mV", step=0.1)
        st.slider("Resistencia total del circuito (Ω)", 0.1, 5.0, key="mRt", step=0.05)
        st.slider("Campo del imán sobre el alambre (mT)", 20.0, 500.0, key="mB", step=5.0)
        st.slider("Radio del alambre (cm)", 0.3, 3.0, key="mR", step=0.1)
        st.slider("Inercia (×10⁻⁷ kg·m²)", 0.05, 5.0, key="mJ", step=0.05)
        st.slider("Fricción (×10⁻⁷ N·m·s)", 0.05, 20.0, key="mb", step=0.05)
        st.number_input("Tu medición: vueltas por segundo (0 = sin dato)", 0.0, 200.0,
                        key="mmed", step=0.5)
    Bm, Rm = st.session_state["mB"] * 1e-3, st.session_state["mR"] * 1e-2
    Jm, bm = st.session_state["mJ"] * 1e-7, st.session_state["mb"] * 1e-7
    tau0 = Jm / (bm + (Bm * Rm * Rm / 2) ** 2 / st.session_state["mRt"])
    res = fx.motor(st.session_state["mV"], st.session_state["mRt"], Bm, Rm, Jm, bm,
                   5 * tau0, 2000)

    with m2:
        k1, k2, k3 = st.columns(3)
        k1.metric("Velocidad estacionaria", f"{res['rev_s']:.3g} vueltas/s")
        k2.metric("Tiempo para arrancar (τ)", f"{res['tau']:.3g} s")
        k3.metric("Corriente al arrancar", f"{res['I0']:.3g} A")

        th_tot = float(res["theta"][-1])
        n_fr_m = int(np.clip(th_tot / 0.5, 60, 400))
        ii = np.linspace(0, len(res["t"]) - 1, n_fr_m).astype(int)
        ang_f = res["theta"][ii]
        figm = make_subplots(rows=1, cols=2, column_widths=[0.45, 0.55],
                             subplot_titles=("Vista desde arriba", "Velocidad angular"),
                             specs=[[{"type": "xy"}, {"type": "xy"}]])
        tt = np.linspace(0, 2 * np.pi, 200)
        figm.add_trace(go.Scatter(x=np.cos(tt), y=np.sin(tt), mode="lines",
                                  line=dict(color=C_B, width=3), showlegend=False), row=1, col=1)
        figm.add_trace(go.Scatter(x=[0, math.cos(ang_f[0])], y=[0, math.sin(ang_f[0])],
                                  mode="lines+markers", line=dict(color=C_E, width=6),
                                  marker=dict(size=[4, 12]), showlegend=False), row=1, col=1)
        figm.add_trace(go.Scatter(x=res["t"], y=res["w"], mode="lines", name="simulación",
                                  line=dict(color=C_OK, width=3)), row=1, col=2)
        figm.add_trace(go.Scatter(x=[res["t"][0], res["t"][-1]], y=[res["w_ss"]] * 2, mode="lines",
                                  name="valor final", line=dict(color="white", dash="dot", width=1)),
                       row=1, col=2)
        figm.update_xaxes(range=[-1.2, 1.2], visible=False, row=1, col=1)
        figm.update_yaxes(range=[-1.2, 1.2], visible=False, scaleanchor="x", row=1, col=1)
        figm.update_xaxes(title_text="t (s)", row=1, col=2)
        figm.update_yaxes(title_text="ω (rad/s)", row=1, col=2)
        figm.frames = [go.Frame(name=str(k), traces=[1],
                                data=[go.Scatter(x=[0, math.cos(a)], y=[0, math.sin(a)],
                                                 mode="lines+markers",
                                                 line=dict(color=C_E, width=6),
                                                 marker=dict(size=[4, 12]))])
                       for k, a in enumerate(ang_f)]
        dur = max(20, int(1000 * res["t"][-1] / n_fr_m * 5))  # cámara lenta ×5
        layout_oscuro(figm, h=None, top=80)
        figm.update_layout(legend=dict(x=0.99, y=0.06, xanchor="right", yanchor="bottom",
                                       bgcolor="rgba(11,23,34,0.7)"))
        mostrar_animado(figm, [str(k) for k in range(len(ang_f))], 560, dur, "motor")
        st.caption("El reproductor va en cámara lenta (×5 por defecto). ⛶ abre la pantalla completa.")

    st.markdown("**Comparación con tu motor real**")
    if st.session_state["mmed"] > 0:
        w_med = st.session_state["mmed"] * 2 * math.pi
        err = abs(res["rev_s"] - st.session_state["mmed"]) / st.session_state["mmed"] * 100
        b_imp = fx.friccion_implicita(st.session_state["mV"], st.session_state["mRt"], Bm, Rm, w_med)
        cc1, cc2, cc3 = st.columns(3)
        cc1.metric("Modelo", f"{res['rev_s']:.3g} vueltas/s")
        cc2.metric("Medido", f"{st.session_state['mmed']:.3g} vueltas/s")
        cc3.metric("Diferencia", f"{err:.1f} %")
        if b_imp > 0:
            st.caption(f"Para que el modelo coincida con tu medición, la fricción debería ser "
                       f"unos {b_imp * 1e7:.2f} ×10⁻⁷ N·m·s. Es un dato útil, pero la fricción "
                       f"real es difícil de medir directamente.")
        else:
            st.caption("Con estos datos la fricción necesaria sale negativa: revisa el voltaje, la "
                       "resistencia o el campo, porque el motor no podría girar tan rápido.")
    else:
        st.caption("Graba tu motor en cámara lenta, cuenta las vueltas por segundo e ingrésalas "
                   "arriba para compararlas con el modelo.")
    st.caption(f"Comprobación numérica: el error máximo de RK4 frente a la solución exacta del "
               f"motor es {res['err_max']:.1e} (relativo a la velocidad final). "
               "El modelo supone campo axial uniforme y fricción lineal, por lo que es una "
               "aproximación del motor real.")

# ================================================================= TAB 5
with tab5:
    st.markdown("#### La idea en pocas líneas")
    st.markdown(
        "Una carga **q** que se mueve con velocidad **v** en campos eléctrico **E** y magnético "
        "**B** recibe la fuerza de Lorentz:")
    st.latex(r"\vec F = q\,(\vec E + \vec v \times \vec B)")
    st.markdown(
        "- **Solo B:** la fuerza es perpendicular a la velocidad, así que no cambia la rapidez, "
        "solo la dirección. La partícula da círculos de radio")
    st.latex(r"r = \frac{m\,v_\perp}{|q|\,B}, \qquad \omega = \frac{|q|\,B}{m}")
    st.markdown("- **Solo E:** la partícula se acelera con a = qE/m, como una pelota en caída libre.")
    st.markdown("- **E y B cruzados:** el círculo se desplaza de lado con velocidad de deriva")
    st.latex(r"v_d = \frac{E}{B}")
    st.markdown("- **Motor:** muchas cargas en un alambre de longitud L con corriente I producen")
    st.latex(r"\vec F = I\,\vec L \times \vec B")
    st.markdown("#### ¿Qué hace RK4?")
    st.markdown(
        "Para avanzar un instante dt, Euler mira la pendiente solo al inicio. RK4 mira la "
        "pendiente en cuatro puntos del intervalo (inicio, dos puntos intermedios y final) y "
        "los promedia con pesos 1, 2, 2, 1. Así el error baja con dt⁴ en lugar de dt.")
    st.markdown("#### Qué simplifica este modelo")
    st.markdown("- Sin relatividad (por eso el aviso al superar el 10 % de c).\n"
                "- Sin radiación ni choques; la partícula está sola.\n"
                "- Campos uniformes, salvo en la botella magnética.\n"
                "- Motor con campo axial uniforme y fricción lineal.")
