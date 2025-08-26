# ============ CRONÓMETRO ============
if "cronometro" not in st.session_state:
    st.session_state.cronometro = {
        "activo": False,
        "pausado": False,
        "start_time": None,
        "elapsed_time": 0  # en segundos
    }

c1, c2, c3, c4 = st.columns(4)

if c1.button("▶️ Iniciar"):
    st.session_state.cronometro["activo"] = True
    st.session_state.cronometro["pausado"] = False
    st.session_state.cronometro["elapsed_time"] = 0
    st.session_state.cronometro["start_time"] = time.time()
    st.success("⏱️ Partido iniciado")

if c2.button("⏸️ Pausar"):
    if st.session_state.cronometro["activo"] and not st.session_state.cronometro["pausado"]:
        st.session_state.cronometro["elapsed_time"] += time.time() - st.session_state.cronometro["start_time"]
        st.session_state.cronometro["pausado"] = True
        st.success("⏸️ Cronómetro pausado")

if c3.button("🔄 Reanudar"):
    if st.session_state.cronometro["activo"] and st.session_state.cronometro["pausado"]:
        st.session_state.cronometro["start_time"] = time.time()
        st.session_state.cronometro["pausado"] = False
        st.success("▶️ Cronómetro reanudado")

if c4.button("⏹️ Detener"):
    st.session_state.cronometro["activo"] = False
    st.session_state.cronometro["pausado"] = False
    st.session_state.cronometro["elapsed_time"] = 0
    st.session_state.cronometro["start_time"] = None
    st.success("🛑 Cronómetro detenido")

# Calcular tiempo actual
minuto_actual = 0
tiempo_formateado = "00:00"
if st.session_state.cronometro["activo"]:
    if st.session_state.cronometro["pausado"]:
        total_seconds = st.session_state.cronometro["elapsed_time"]
    else:
        total_seconds = st.session_state.cronometro["elapsed_time"] + (time.time() - st.session_state.cronometro["start_time"])
    minutos, segundos = divmod(int(total_seconds), 60)
    minuto_actual = minutos
    tiempo_formateado = f"{minutos:02d}:{segundos:02d}"

st.markdown(f"### ⏱ Tiempo actual: {tiempo_formateado} (min {minuto_actual}')")
