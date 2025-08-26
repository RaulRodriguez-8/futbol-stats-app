import streamlit as st
import pandas as pd
from datetime import date, datetime
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
# Funciones DB
# ==============================
def crear_partido(local, visitante, competicion, jornada, lugar, fecha):
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

    if st.button("Crear partido"):
        p = crear_partido(local, visitante, competicion, jornada, lugar, fecha)
        if p:
            st.success(f"✅ Partido creado: {p['nombre']}")
        else:
            st.error("⚠️ Error al crear el partido.")

# ==============================
# 📂 PARTIDOS GUARDADOS
# ==============================
elif menu == "📂 Partidos almacenados":
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
        f"## 📌 {partido['nombre']} — {partido['competicion']} "
        f"— Jornada {partido.get('jornada','')} "
        f"— {partido.get('fecha','')} — {partido.get('lugar','')}"
    )

    # ============ CRONÓMETRO ============
    if "cronometro" not in st.session_state:
        st.session_state.cronometro = {
            "activo": False,
            "pausado": False,
            "start_time": None,
            "elapsed_time": 0
        }

    minuto_actual = 0
    tiempo_formateado = "00:00"
    if st.session_state.cronometro["activo"]:
        if st.session_state.cronometro["pausado"]:
            total_seconds = st.session_state.cronometro["elapsed_time"]
        else:
            total_seconds = (
                st.session_state.cronometro["elapsed_time"]
                + (time.time() - st.session_state.cronometro["start_time"])
            )
        minutos, segundos = divmod(int(total_seconds), 60)
        minuto_actual = minutos
        tiempo_formateado = f"{minutos:02d}:{segundos:02d}"

    # ============ TABLERO DE CONTROL ============
    st.markdown("## 🎛 Tablero de control")

    acciones = {
        "🚀 Tiro a puerta": "Tiro a puerta",
        "🎯 Llegada": "Llegada",
        "❌ Falta": "Falta",
        "📦 Centro": "Centro",
        "✅ 2ª jugada ganada": "Segunda jugada (ganada)",
        "❌ 2ª jugada perdida": "Segunda jugada (perdida)",
    }

    col_local, col_centro, col_visitante = st.columns([3,2,3])

    # --- Columna Local ---
    with col_local:
        st.subheader(f"🏠 {partido['local']}")
        for emoji, accion in acciones.items():
            if st.button(f"{emoji} {accion}", key=f"{accion}_{partido['local']}"):
                insertar_evento(int(partido_sel), partido["local"], accion, minuto_actual, tiempo_formateado)
                st.success(f"{accion} registrado para {partido['local']} en {tiempo_formateado}")

    # --- Columna Centro (Cronómetro + Marcador) ---
    with col_centro:
        st.subheader("⏱ Cronómetro")
        st.markdown(f"### {tiempo_formateado} (min {minuto_actual}')")

        c1, c2, c3, c4 = st.columns(4)
        if c1.button("▶️", key="start"):
            st.session_state.cronometro = {
                "activo": True,
                "pausado": False,
                "start_time": time.time(),
                "elapsed_time": 0
            }
            st.success("Partido iniciado")

        if c2.button("⏸", key="pause"):
            if st.session_state.cronometro["activo"] and not st.session_state.cronometro["pausado"]:
                st.session_state.cronometro["elapsed_time"] += time.time() - st.session_state.cronometro["start_time"]
                st.session_state.cronometro["pausado"] = True
                st.warning("Cronómetro pausado")

        if c3.button("🔄", key="resume"):
            if st.session_state.cronometro["activo"] and st.session_state.cronometro["pausado"]:
                st.session_state.cronometro["start_time"] = time.time()
                st.session_state.cronometro["pausado"] = False
                st.info("Cronómetro reanudado")

        if c4.button("⏹", key="stop"):
            st.session_state.cronometro = {
                "activo": False,
                "pausado": False,
                "start_time": None,
                "elapsed_time": 0
            }
            st.error("Partido detenido")

        # --- Marcador ---
        st.subheader("⚽ Marcador")
        goles_local = partido.get("goles_local", 0)
        goles_visitante = partido.get("goles_visitante", 0)

        mcol1, mcol2, mcol3 = st.columns([3,2,3])
        with mcol1:
            if st.button("➖", key="menos_local") and goles_local > 0:
                goles_local -= 1
                supabase.table("partidos").update({"goles_local": goles_local}).eq("id", partido_sel).execute()
            st.markdown(f"## {goles_local}")
            if st.button("➕", key="mas_local"):
                goles_local += 1
                supabase.table("partidos").update({"goles_local": goles_local}).eq("id", partido_sel).execute()
                insertar_evento(int(partido_sel), partido["local"], "Gol", minuto_actual, tiempo_formateado)

        with mcol2:
            st.markdown(f"### {partido['local']} - {partido['visitante']}")

        with mcol3:
            if st.button("➖", key="menos_visitante") and goles_visitante > 0:
                goles_visitante -= 1
                supabase.table("partidos").update({"goles_visitante": goles_visitante}).eq("id", partido_sel).execute()
            st.markdown(f"## {goles_visitante}")
            if st.button("➕", key="mas_visitante"):
                goles_visitante += 1
                supabase.table("partidos").update({"goles_visitante": goles_visitante}).eq("id", partido_sel).execute()
                insertar_evento(int(partido_sel), partido["visitante"], "Gol", minuto_actual, tiempo_formateado)

    # --- Columna Visitante ---
    with col_visitante:
        st.subheader(f"🚩 {partido['visitante']}")
        for emoji, accion in acciones.items():
            if st.button(f"{emoji} {accion}", key=f"{accion}_{partido['visitante']}"):
                insertar_evento(int(partido_sel), partido["visitante"], accion, minuto_actual, tiempo_formateado)
                st.success(f"{accion} registrado para {partido['visitante']} en {tiempo_formateado}")

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
            colL.table(resumen[resumen["equipo"]==partido["local"]][["accion","Cantidad"]].set_index("accion"))
        if not resumen[resumen["equipo"]==partido["visitante"]].empty:
            colV.subheader(partido["visitante"])
            colV.table(resumen[resumen["equipo"]==partido["visitante"]][["accion","Cantidad"]].set_index("accion"))
