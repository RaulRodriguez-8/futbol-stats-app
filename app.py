import streamlit as st
import pandas as pd
from datetime import date, datetime, timezone
from supabase import create_client, Client
import time

# ==============================
# Conexión Supabase
# ==============================
@st.cache_resource
def get_client() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_client()

# ==============================
# Helpers de tiempo persistente
# ==============================
def ahora_utc():
    return datetime.now(timezone.utc)

def compute_clock_from_db(partido: dict):
    """
    Calcula (minuto_actual, 'MM:SS') usando los campos persistidos en DB:
    clock_elapsed (seg acumulados), clock_active, clock_paused, clock_start (UTC).
    """
    elapsed = partido.get("clock_elapsed", 0) or 0
    active  = partido.get("clock_active", False)
    paused  = partido.get("clock_paused", False)
    start   = partido.get("clock_start", None)

    total_seconds = int(elapsed)
    if active and not paused and start:
        # start puede venir como str ISO o datetime
        if isinstance(start, str):
            start = datetime.fromisoformat(start.replace("Z", "+00:00"))
        delta = (ahora_utc() - start).total_seconds()
        total_seconds += max(0, int(delta))

    minutos, segundos = divmod(int(total_seconds), 60)
    return minutos, f"{minutos:02d}:{segundos:02d}"

def set_clock_state(pid: int, **fields):
    supabase.table("partidos").update(fields).eq("id", pid).execute()

# ==============================
# Funciones DB
# ==============================
def crear_partido(local, visitante, competicion, jornada, lugar, fecha, acciones):
    nombre = f"{local} vs {visitante}"
    data = {
        "nombre": nombre,
        "local": local,
        "visitante": visitante,
        "competicion": competicion,
        "jornada": jornada,
        "lugar": lugar,
        "fecha": str(fecha),
        "goles_local": 0,
        "goles_visitante": 0,
        "acciones": acciones,
        # estado inicial del reloj persistente
        "clock_active": False,
        "clock_paused": False,
        "clock_start": None,
        "clock_elapsed": 0,
    }
    res = supabase.table("partidos").insert(data).execute()
    return res.data[0] if res.data else None

def listar_partidos():
    res = supabase.table("partidos").select("*").order("id", desc=True).execute()
    return pd.DataFrame(res.data or [])

def get_partido(pid: int):
    res = supabase.table("partidos").select("*").eq("id", pid).single().execute()
    return res.data

def insertar_evento(pid, equipo, accion, minuto, tiempo_exact):
    ts = datetime.now().isoformat(timespec="seconds")
    data = {
        "partido_id": pid,
        "equipo": equipo,
        "accion": accion,
        "parte": "Automático",
        "minuto": minuto,
        "tiempo_exact": tiempo_exact,
        "timestamp": ts,
    }
    supabase.table("eventos").insert(data).execute()

def eventos_por_partido(pid):
    res = supabase.table("eventos").select("*").eq("partido_id", pid).order("id").execute()
    return pd.DataFrame(res.data or [])

# ==============================
# Layout App
# ==============================
st.set_page_config(page_title="Registro en directo - Fútbol", layout="wide")
st.title("⚽ Registro en directo - Fútbol")

menu = st.sidebar.radio("Menú", ["➕ Añadir partido nuevo", "📂 Partidos almacenados"])

# ==============================
# ➕ NUEVO PARTIDO
# ==============================
if menu == "➕ Añadir partido nuevo":
    st.subheader("➕ Crear nuevo partido")
    c1, c2 = st.columns(2)
    local = c1.text_input("Equipo Local", value="Mi Equipo")
    visitante = c2.text_input("Equipo Visitante", value="Rival")

    c3, c4 = st.columns(2)
    competicion = c3.text_input("Competición", value="")
    jornada = c4.text_input("Jornada", value="")

    lugar = st.text_input("Lugar", value="")
    fecha = st.date_input("Fecha", value=date.today())

    acciones_input = st.text_area(
        "Acciones a registrar (separadas por coma)",
        value="Tiro a puerta, Llegada, Falta, Centro"
    )

    if st.button("Crear partido"):
        acciones_lista = [a.strip() for a in acciones_input.split(",") if a.strip()]
        p = crear_partido(local, visitante, competicion, jornada, lugar, fecha, acciones_lista)
        if p:
            st.success(f"✅ Partido creado: {p['nombre']}")
        else:
            st.error("⚠️ Error al crear el partido.")

# ==============================
# 📂 PARTIDOS GUARDADOS
# ==============================
elif menu == "📂 Partidos almacenados":
    # (Opcional) auto-refresh visual cada 10s para ver avanzar el reloj sin tocar nada
    st.markdown('<meta http-equiv="refresh" content="10">', unsafe_allow_html=True)

    partidos_df = listar_partidos()
    if partidos_df.empty:
        st.info("No hay partidos aún.")
        st.stop()

    partido_sel = st.selectbox(
        "Selecciona un partido",
        options=partidos_df["id"],
        format_func=lambda i: partidos_df.loc[partidos_df["id"]==i, "nombre"].values[0]
    )
    partido = get_partido(int(partido_sel))

    st.markdown(
        f"## 📌 {partido['nombre']} — {partido.get('competicion','')} "
        f"— Jornada {partido.get('jornada','')} "
        f"— {partido.get('fecha','')} — {partido.get('lugar','')}"
    )

    # Calcula tiempo actual SIEMPRE desde DB (persistente)
    minuto_actual, tiempo_formateado = compute_clock_from_db(partido)

    # ============ TABLERO DE CONTROL ============
    st.markdown("## 🎛 Tablero de control")

    acciones = partido.get("acciones", ["Tiro a puerta", "Llegada", "Falta", "Centro"])

    col_local, col_centro, col_visitante = st.columns([3,2,3])

    # --- Columna Local ---
    with col_local:
        st.subheader(f"🏠 {partido['local']}")
        for accion in acciones:
            if st.button(f"{accion} ({partido['local']})", key=f"{accion}_{partido['local']}"):
                # recalcula tiempo por si hubo cambio durante el render
                m, t = compute_clock_from_db(get_partido(int(partido_sel)))
                insertar_evento(int(partido_sel), partido["local"], accion, m, t)
                st.success(f"{accion} registrado para {partido['local']} en {t}")

    # --- Columna Centro (Cronómetro + Marcador persistentes) ---
    with col_centro:
        st.subheader("⏱ Cronómetro")
        st.markdown(f"### {tiempo_formateado} (min {minuto_actual}')")

        c1, c2, c3, c4 = st.columns(4)
        if c1.button("▶️", key="start"):
            # iniciar desde cero
            set_clock_state(
                int(partido_sel),
                clock_active=True,
                clock_paused=False,
                clock_elapsed=0,
                clock_start=ahora_utc().isoformat()
            )
            st.experimental_rerun()

        if c2.button("⏸", key="pause"):
            p = get_partido(int(partido_sel))
            # acumular exacto
            elapsed = p.get("clock_elapsed", 0) or 0
            start = p.get("clock_start")
            if isinstance(start, str) and start:
                start = datetime.fromisoformat(start.replace("Z", "+00:00"))
            if p.get("clock_active") and not p.get("clock_paused") and start:
                elapsed += max(0, int((ahora_utc() - start).total_seconds()))
            set_clock_state(
                int(partido_sel),
                clock_active=True,
                clock_paused=True,
                clock_elapsed=elapsed,
                clock_start=None
            )
            st.experimental_rerun()

        if c3.button("🔄", key="resume"):
            set_clock_state(
                int(partido_sel),
                clock_active=True,
                clock_paused=False,
                clock_start=ahora_utc().isoformat()
            )
            st.experimental_rerun()

        if c4.button("⏹", key="stop"):
            set_clock_state(
                int(partido_sel),
                clock_active=False,
                clock_paused=False,
                clock_elapsed=0,
                clock_start=None
            )
            st.experimental_rerun()

        # --- Marcador (persistente) ---
        st.subheader("⚽ Marcador")
        goles_local = partido.get("goles_local", 0) or 0
        goles_visitante = partido.get("goles_visitante", 0) or 0

        mcol1, mcol2, mcol3 = st.columns([3,2,3])
        with mcol1:
            if st.button("➖", key="menos_local") and goles_local > 0:
                supabase.table("partidos").update({"goles_local": goles_local - 1}).eq("id", partido_sel).execute()
                st.experimental_rerun()
            st.markdown(f"## {goles_local}")
            if st.button("➕", key="mas_local"):
                supabase.table("partidos").update({"goles_local": goles_local + 1}).eq("id", partido_sel).execute()
                # loguea gol como evento
                m, t = compute_clock_from_db(get_partido(int(partido_sel)))
                insertar_evento(int(partido_sel), partido["local"], "Gol", m, t)
                st.experimental_rerun()

        with mcol2:
            st.markdown(f"### {partido['local']} - {partido['visitante']}")

        with mcol3:
            if st.button("➖", key="menos_visitante") and goles_visitante > 0:
                supabase.table("partidos").update({"goles_visitante": goles_visitante - 1}).eq("id", partido_sel).execute()
                st.experimental_rerun()
            st.markdown(f"## {goles_visitante}")
            if st.button("➕", key="mas_visitante"):
                supabase.table("partidos").update({"goles_visitante": goles_visitante + 1}).eq("id", partido_sel).execute()
                # loguea gol como evento
                m, t = compute_clock_from_db(get_partido(int(partido_sel)))
                insertar_evento(int(partido_sel), partido["visitante"], "Gol", m, t)
                st.experimental_rerun()

    # --- Columna Visitante ---
    with col_visitante:
        st.subheader(f"🚩 {partido['visitante']}")
        for accion in acciones:
            if st.button(f"{accion} ({partido['visitante']})", key=f"{accion}_{partido['visitante']}"):
                m, t = compute_clock_from_db(get_partido(int(partido_sel)))
                insertar_evento(int(partido_sel), partido["visitante"], accion, m, t)
                st.success(f"{accion} registrado para {partido['visitante']} en {t}")

    # ============ DATOS DEL PARTIDO ============
    df = eventos_por_partido(int(partido_sel))
    if not df.empty:
        st.markdown("### 📊 Eventos del partido")
        st.dataframe(df, use_container_width=True, height=300)

        st.markdown("### 📈 Resumen por equipo")
        resumen = (
            df.groupby(["equipo", "accion"])
              .size()
              .reset_index(name="Cantidad")
              .sort_values(["equipo", "Cantidad"], ascending=[True, False])
        )

        colL, colV = st.columns(2)

        if not resumen[resumen["equipo"]==partido["local"]].empty:
            colL.subheader(partido["local"])
            tabla_local = resumen[resumen["equipo"]==partido["local"]][["accion","Cantidad"]].set_index("accion")
            colL.table(tabla_local)
            colL.bar_chart(tabla_local)

        if not resumen[resumen["equipo"]==partido["visitante"]].empty:
            colV.subheader(partido["visitante"])
            tabla_visitante = resumen[resumen["equipo"]==partido["visitante"]][["accion","Cantidad"]].set_index("accion")
            colV.table(tabla_visitante)
            colV.bar_chart(tabla_visitante)

        # --- Gráfico comparativo único ---
        st.markdown("### ⚔️ Comparativa de equipos")
        comparativa = resumen.pivot(index="accion", columns="equipo", values="Cantidad").fillna(0)
        st.bar_chart(comparativa)

        # --- Exportar datos ---
        st.markdown("### 📥 Exportar datos del partido")
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Descargar en CSV",
            data=csv,
            file_name=f"{partido['nombre'].replace(' ', '_')}.csv",
            mime="text/csv",
        )
