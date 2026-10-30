"""
fisica.py - Núcleo físico y numérico del simulador (sin interfaz).

Resuelve el movimiento de una partícula cargada bajo la fuerza de Lorentz,
    m dv/dt = q (E + v x B),
con el método RK4 (y Euler explícito para comparar), y contiene las
soluciones analíticas usadas para validar. También incluye el modelo del
motor homopolar. Todo en unidades SI.
"""
from __future__ import annotations

import math
import numpy as np

E_CARGA = 1.602176634e-19      # C
M_PROTON = 1.67262192369e-27   # kg
M_ELECTRON = 9.1093837015e-31  # kg
C_LUZ = 2.99792458e8           # m/s

# nombre -> (carga en unidades de e, masa en kg)
PARTICULAS = {
    "Electrón": (-1.0, M_ELECTRON),
    "Protón": (1.0, M_PROTON),
    "Partícula alfa": (2.0, 6.6446573357e-27),
    "Positrón": (1.0, M_ELECTRON),
}


# ---------------------------------------------------------------- campos
def campo_B(x, y, z, B0, L):
    """Campo magnético. L=None: uniforme en z. Con L: 'botella magnética'
    Bz = B0 (1 + z^2/L^2) y componentes radiales que cumplen div B = 0."""
    if L is None:
        return 0.0, 0.0, B0
    k = B0 / (L * L)
    return -k * x * z, -k * y * z, B0 * (1.0 + (z / L) ** 2)


def _deriv(s, qm, Ex, Ey, Ez, B0, L):
    x, y, z, vx, vy, vz = s
    Bx, By, Bz = campo_B(x, y, z, B0, L)
    ax = qm * (Ex + vy * Bz - vz * By)
    ay = qm * (Ey + vz * Bx - vx * Bz)
    az = qm * (Ez + vx * By - vy * Bx)
    return (vx, vy, vz, ax, ay, az)


# ------------------------------------------------------------ integración
def integrar(s0, q, m, E, B0, L, t_fin, n, metodo="RK4"):
    """Integra n pasos de tamaño t_fin/n. Devuelve (t, estado) con estado de
    forma (n+1, 6) = [x, y, z, vx, vy, vz]."""
    qm = q / m
    Ex, Ey, Ez = E
    dt = t_fin / n
    out = np.empty((n + 1, 6))
    out[0] = s0
    s = tuple(float(v) for v in s0)

    def f(st):
        return _deriv(st, qm, Ex, Ey, Ez, B0, L)

    i = 0
    try:
        if metodo == "Euler":
            for i in range(n):
                k1 = f(s)
                s = tuple(a + dt * k for a, k in zip(s, k1))
                out[i + 1] = s
        else:  # RK4
            h2, h6 = 0.5 * dt, dt / 6.0
            for i in range(n):
                k1 = f(s)
                k2 = f(tuple(a + h2 * k for a, k in zip(s, k1)))
                k3 = f(tuple(a + h2 * k for a, k in zip(s, k2)))
                k4 = f(tuple(a + dt * k for a, k in zip(s, k3)))
                s = tuple(a + h6 * (p + 2 * u + 2 * v + w)
                          for a, p, u, v, w in zip(s, k1, k2, k3, k4))
                out[i + 1] = s
    except OverflowError:
        # el método diverge (típico de Euler en campos fuertes): el resto queda en NaN
        out[i + 1:] = np.nan
    out[~np.isfinite(out)] = np.nan
    return np.linspace(0.0, t_fin, n + 1), out


# ------------------------------------------------- solución analítica (E, B uniformes)
def analitica(t, q, m, E, B0, r0, v0):
    """Solución exacta con B = B0 z^ y E constante. Devuelve (len(t), 6)."""
    qm = q / m
    Ex, Ey, Ez = E
    x0, y0, z0 = r0
    vx0, vy0, vz0 = v0
    z = z0 + vz0 * t + 0.5 * qm * Ez * t ** 2
    vz = vz0 + qm * Ez * t
    if abs(B0) < 1e-15:
        x = x0 + vx0 * t + 0.5 * qm * Ex * t ** 2
        y = y0 + vy0 * t + 0.5 * qm * Ey * t ** 2
        vx = vx0 + qm * Ex * t
        vy = vy0 + qm * Ey * t
        return np.column_stack([x, y, z, vx, vy, vz])
    w = qm * B0                       # frecuencia angular con signo
    ud = -1j * (Ex + 1j * Ey) / B0    # velocidad de deriva E x B / B^2
    u0 = vx0 + 1j * vy0
    e = np.exp(-1j * w * t)
    u = ud + (u0 - ud) * e
    zc = (x0 + 1j * y0) + ud * t + (u0 - ud) * (1 - e) / (1j * w)
    return np.column_stack([zc.real, zc.imag, z, u.real, u.imag, vz])


def teoria(q, m, E, B0, v0):
    """Valores teóricos de referencia para B uniforme > 0."""
    if B0 <= 0:
        return None
    Ex, Ey, Ez = E
    w = q * B0 / m
    T = 2 * math.pi / abs(w)
    ud = -1j * (Ex + 1j * Ey) / B0
    u0 = v0[0] + 1j * v0[1]
    return {
        "w": abs(w), "T": T, "f": 1 / T,
        "r": abs(u0 - ud) / abs(w),
        "deriva": abs(ud),
        "paso": v0[2] * T if abs(Ez) < 1e-12 else None,
        "sentido": "antihorario" if w < 0 else "horario",  # visto desde +z (por -w en u)
    }


def _cruces_ascendentes(t, d):
    idx = np.where((d[:-1] < 0) & (d[1:] >= 0))[0]
    return t[idx] + (0 - d[idx]) * (t[idx + 1] - t[idx]) / (d[idx + 1] - d[idx])


def medir(t, s, ncyc):
    """Magnitudes medidas SOLO a partir de la simulación (sin usar la teoría)."""
    t_fin = t[-1]
    zc = s[:, 0] + 1j * s[:, 1]
    deriva_sim = abs(zc[-1] - zc[0]) / t_fin
    vel_drift = (zc[-1] - zc[0]) / t_fin
    rel = zc[:-1] - vel_drift * t[:-1]
    centro = rel.mean()
    r_sim = float(np.mean(np.abs(rel - centro)))
    # periodo: cruces ascendentes de la componente de velocidad con más amplitud
    comp = s[:-1, 3] if np.ptp(s[:, 3]) >= np.ptp(s[:, 4]) else s[:-1, 4]
    cr = _cruces_ascendentes(t[:-1], comp - comp.mean())
    T_sim = float(np.mean(np.diff(cr))) if len(cr) >= 2 else float("nan")
    paso_sim = (s[-1, 2] - s[0, 2]) / ncyc
    return {"deriva": deriva_sim, "r": r_sim, "T": T_sim, "paso": paso_sim}


def energia_relativa(t, s, q, m, E):
    """Error relativo de la energía total  K - q E.r  (se conserva: B no hace trabajo)."""
    with np.errstate(over="ignore", invalid="ignore"):
        v2 = s[:, 3] ** 2 + s[:, 4] ** 2 + s[:, 5] ** 2
        K = 0.5 * m * v2
        U = -q * (E[0] * s[:, 0] + E[1] * s[:, 1] + E[2] * s[:, 2])
        Et = K + U
        escala = K[0] if np.isnan(K).all() else max(K[0], np.nanmax(K))
        if not escala > 0:
            escala = 1.0
        rel = (Et - Et[0]) / escala
    # valores absurdos (método divergido) se descartan para no aplastar la gráfica
    rel[np.abs(s).max(axis=1) > 1e9] = np.nan
    return rel, K


def convergencia(q, m, E, B0, s0, ncyc=3):
    """Error máximo de posición vs. solución analítica en función del paso dt.
    Euler necesita pasos mucho más finos que RK4 para entrar en su régimen
    asintótico, por eso cada método usa su propio rango de pasos."""
    T = 2 * math.pi / abs(q * B0 / m)
    rangos = {"Euler": (200, 400, 800, 1600, 3200), "RK4": (10, 15, 20, 30, 40, 60, 80)}
    res = {}
    for metodo, ppcs in rangos.items():
        dts, errs = [], []
        for p in ppcs:
            t, s = integrar(s0, q, m, E, B0, None, ncyc * T, ncyc * p, metodo)
            ref = analitica(t, q, m, E, B0, s0[:3], s0[3:])
            err = np.max(np.linalg.norm(s[:, :3] - ref[:, :3], axis=1))
            dts.append(T / p)
            errs.append(max(err, 1e-300))
        res[metodo] = {"dt": dts, "err": errs,
                       "pendiente": float(np.polyfit(np.log(dts), np.log(errs), 1)[0])}
    return res


# ------------------------------------------------------- motor homopolar
def motor(V, Rt, B, R, J, b, t_fin, n):
    """Motor homopolar idealizado: radio R en campo axial uniforme B.
        fem inducida  e = K w ,  K = B R^2 / 2
        corriente     I = (V - K w) / Rt
        torque        tau = K I
        dinámica      J dw/dt = K I - b w
    Se integra (w, theta) con RK4 y se compara con la solución exacta."""
    K = B * R * R / 2.0
    dt = t_fin / n

    def f(w, th):
        return ((K * (V - K * w) / Rt - b * w) / J, w)

    w, th = 0.0, 0.0
    W = np.empty(n + 1); TH = np.empty(n + 1)
    W[0], TH[0] = w, th
    for i in range(n):
        a1, b1 = f(w, th)
        a2, b2 = f(w + 0.5 * dt * a1, th + 0.5 * dt * b1)
        a3, b3 = f(w + 0.5 * dt * a2, th + 0.5 * dt * b2)
        a4, b4 = f(w + dt * a3, th + dt * b3)
        w += dt / 6 * (a1 + 2 * a2 + 2 * a3 + a4)
        th += dt / 6 * (b1 + 2 * b2 + 2 * b3 + b4)
        W[i + 1], TH[i + 1] = w, th
    t = np.linspace(0, t_fin, n + 1)
    den = b + K * K / Rt
    w_ss = K * V / Rt / den
    tau = J / den
    w_ex = w_ss * (1 - np.exp(-t / tau))
    return {
        "t": t, "w": W, "theta": TH, "I": (V - K * W) / Rt, "torque": K * (V - K * W) / Rt,
        "w_ss": w_ss, "tau": tau, "K": K, "I0": V / Rt,
        "err_max": float(np.max(np.abs(W - w_ex))) / w_ss,
        "rev_s": w_ss / (2 * math.pi),
    }


def friccion_implicita(V, Rt, B, R, w_med):
    """b que reproduce una velocidad estacionaria medida w_med (rad/s)."""
    K = B * R * R / 2.0
    return K * (V - K * w_med) / (Rt * w_med)


# ------------------------------------------------------------- fuerzas (para dibujar flechas)
def fuerzas(s, q, E, B0, L):
    """Fuerza eléctrica qE y fuerza magnética q v x B en cada punto de la trayectoria.
    Devuelve dos arreglos (n, 3) en newtons."""
    P, V = s[:, :3], s[:, 3:6]
    if L is None:
        B = np.zeros_like(P)
        B[:, 2] = B0
    else:
        k = B0 / (L * L)
        B = np.column_stack([-k * P[:, 0] * P[:, 2], -k * P[:, 1] * P[:, 2],
                             B0 * (1.0 + (P[:, 2] / L) ** 2)])
    FB = q * np.cross(V, B)
    FE = np.tile(q * np.asarray(E, dtype=float), (len(P), 1))
    return FE, FB


# ------------------------------------------------------------- campos E y B en el espacio
def campo_E(P, E):
    """Campo eléctrico (uniforme) en cada punto P (n, 3). Devuelve (n, 3) en V/m."""
    P = np.atleast_2d(P)
    return np.tile(np.asarray(E, dtype=float), (len(P), 1))


def campo_B_vec(P, B0, L):
    """Campo magnético en cada punto P (n, 3). Uniforme en z, o botella magnética si se da L.
    Devuelve (n, 3) en teslas."""
    P = np.atleast_2d(np.asarray(P, dtype=float))
    if L is None:
        B = np.zeros_like(P)
        B[:, 2] = B0
        return B
    k = B0 / (L * L)
    return np.column_stack([-k * P[:, 0] * P[:, 2], -k * P[:, 1] * P[:, 2],
                            B0 * (1.0 + (P[:, 2] / L) ** 2)])


def malla_campos(lo, hi, n, E, B0, L):
    """Malla de n x n x n puntos entre lo y hi (SI) con el campo E y B en cada uno.
    Devuelve (puntos, E, B), cada uno de forma (n^3, 3)."""
    ejes = [np.linspace(lo[i], hi[i], n) for i in range(3)]
    G = np.array(np.meshgrid(*ejes, indexing="ij")).reshape(3, -1).T
    return G, campo_E(G, E), campo_B_vec(G, B0, L)


def linea_de_campo(p0, campo, lo, hi, paso, n_max=200):
    """Línea de campo que pasa por p0: se integra dp/ds = campo/|campo| con RK4 (paso de
    longitud fija) en los dos sentidos hasta salir de la caja [lo, hi]. `campo` recibe un
    punto (3,) y devuelve un vector (3,). Devuelve un arreglo (m, 3)."""
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    adelante, atras = [np.asarray(p0, float)], []
    for signo, lista in ((1.0, adelante), (-1.0, atras)):
        p = np.asarray(p0, float).copy()
        for _ in range(n_max):
            def u(x):
                v = np.asarray(campo(x), float)
                nv = np.linalg.norm(v)
                return signo * v / nv if nv > 0 else np.zeros(3)
            k1 = u(p)
            if not k1.any():
                break
            k2 = u(p + 0.5 * paso * k1)
            k3 = u(p + 0.5 * paso * k2)
            k4 = u(p + paso * k3)
            p = p + paso / 6.0 * (k1 + 2 * k2 + 2 * k3 + k4)
            if (not np.isfinite(p).all()) or np.any(p < lo) or np.any(p > hi):
                break
            lista.append(p.copy())
    return np.array(atras[::-1] + adelante)
