import streamlit as st
import pandas as pd
from datetime import date, datetime
from supabase import create_client, Client

# ==============================
# Conexión Supabase (secrets)
# ==============================
@st.cache_resource
def get_client() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_client()

st.set_page_config(page_title="Registro en directo - Fútbol", layout="wide")
st.title("⚽ Registro de datos en directo - Fútbol")

# ==============================
# Utilidades DB
# ==============================
def crear_partido(local: str, visitante: str, competicion: str, f: date):
    nombre = f"{local} vs {visitante}"
    data = {"nombre": nombre, "local": local, "visitante": visitante, "competicion": competicion, "fecha": str(f)}
    res = supabase.table("partidos").insert(data).execute()
    return res.data[0] if res.data else None

def listar_partidos():
    res = supabase.table("partidos").select("*").order("id", desc=True).execute()
    return pd.DataFrame(res.data or [])

def get_partido(pid: int):
    res = supabase.table("partidos").select("*").eq("id", pid).single().execute()
    return res.data

def insertar_evento(pid: int, equipo: str, accion: str, parte: str, minuto: int):
    ts = datetime.now().isoformat(timespec="seconds")
    data = {"partido_id": pid, "equipo": equipo, "accion": accion, "parte": parte, "minuto": int(minuto), "timestamp": ts}
    supabase.table("eventos").insert(data).execute()

def borrar_ultimo_evento(pid: int):
    # obtener último id de ese partido
    res = supabase.table("eventos").select("id").eq("partido_id", pid).order("id", desc=True).limit(1).execute()
    if res.data:
        eid = res.data[0]["id"]
        supabase.table("eventos").delete().eq("id", eid).execute()
        return True
    return False

def eventos_por_partido(pid: int):
    res = supabase.table("eventos").select("id,equipo,accion,parte,minuto,timestamp").eq("partido_id", pid).order("id", desc=True).execute()
    return pd.DataFrame(res.data or [])

# ==============================
# Sidebar: crear/seleccionar partido
# ==============================
st.sidebar.header("🎟️ Partido")

tab_nuevo, tab_existente = st.sidebar.tabs(["Nuevo", "Existente"])

with tab_nuevo:
    st.sidebar.write("Crear nuevo partido")
    c1, c2 = st.sidebar.columns(2)
    local = c1.text_input("Equipo Local", value="Mi Equipo")
    visitante = c2.text_input("Equipo Visitante", value="Rival")
    c3, c4 = st.sidebar.columns(2)
    competicion = c3.text_input("Competición", value="")
    fecha = c4.date_input("Fecha", value=date.today())

    if st.sidebar.button("➕ Crear partido"):
        p = crear_partido(local, visitante, competicion, fecha)
        if p:
            st.sidebar.success(f"Creado: {p['nombre']}")
        else:
            st.sidebar.error("No se pudo crear el partido.")

with tab_existente:
    partidos_df = listar_partidos()
    if partidos_df.empty:
        st.sidebar.info("No hay partidos aún.")
        st.stop()
    partido_sel = st.sidebar.selectbox(
        "Selecciona un partido",
        options=partidos_df["id"],
        format_func=lambda i: f"{partidos_df.loc[partidos_df['id']==i, 'nombre'].values[0]} ({partidos_df.loc[partidos_df['id']==i, 'fecha'].values[0]})"
    )

# Si no hay selección, detenemos
if "partido_sel" not in locals():
    st.info("Crea o selecciona un partido en la barra lateral.")
    st.stop()

partido = get_partido(int(partido_sel))
st.markdown(f"## 📌 {partido['nombre']} — {partido.get('competicion','')} — {partido.get('fecha','')}")

# ==============================
# Controles de registro
# ==============================
st.markdown("### 🎮 Acciones en directo")

top1, top2, top3, top4 = st.columns(4)
equipo_accion = top1.radio("Equipo de la acción", ["Local", "Visitante"], horizontal=True)
parte = top2.selectbox("Parte", ["1ª", "2ª"])
minuto = int(top3.number_input("Minuto", min_value=0, max_value=130, value=0, step=1))
top4.write("")

acciones = {
    "🚀 Tiro a puerta": "Tiro a puerta",
    "🎯 Llegada": "Llegada",
    "❌ Falta": "Falta",
    "📦 Centro": "Centro",
    "✅ 2ª jugada ganada": "Segunda jugada (ganada)",
    "❌ 2ª jugada perdida": "Segunda jugada (perdida)"
}

c1, c2, c3 = st.columns(3)
for i, (emoji, accion) in enumerate(acciones.items()):
    with [c1, c2, c3][i % 3]:
        if st.button(emoji):
            insertar_evento(int(partido_sel), equipo_accion, accion, parte, minuto)
            st.success(f"{emoji} registrada para **{equipo_accion}** en el {minuto}'")

if st.button("↩️ Deshacer último evento"):
    ok = borrar_ultimo_evento(int(partido_sel))
    st.info("Último evento eliminado." if ok else "No hay eventos para borrar.")

# ==============================
# Datos y resúmenes
# ==============================
st.markdown("### 📊 Eventos del partido")
df = eventos_por_partido(int(partido_sel))
st.dataframe(df, use_container_width=True, height=320)

if not df.empty:
    st.markdown("### 📈 Resumen por equipo")
    resumen = (
        df.groupby(["equipo", "accion"])
          .size()
          .reset_index(name="Cantidad")
          .sort_values(["equipo", "Cantidad"], ascending=[True, False])
    )
    colL, colV = st.columns(2)
    if not resumen[resumen["equipo"]=="Local"].empty:
        colL.subheader(f"Local: {partido['local']}")
        colL.table(resumen[resumen["equipo"]=="Local"][["accion","Cantidad"]].set_index("accion"))
    if not resumen[resumen["equipo"]=="Visitante"].empty:
        colV.subheader(f"Visitante: {partido['visitante']}")
        colV.table(resumen[resumen["equipo"]=="Visitante"][["accion","Cantidad"]].set_index("accion"))

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Descargar CSV del partido", csv, f"{partido['nombre'].replace(' ','_')}.csv", "text/csv")

with st.expander("📂 Historial de partidos"):
    if not partidos_df.empty:
        st.dataframe(
            partidos_df.rename(columns={"id":"ID","nombre":"Partido","local":"Local","visitante":"Visitante","competicion":"Competición","fecha":"Fecha"}),
            use_container_width=True
        )
