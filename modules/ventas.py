import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta, date
import calendar
from utils import conectar_google_sheets, ZONA_HORARIA, leer_datos_seguro

# --- CONFIGURACIÓN ---
NOMBRE_HOJA = "LOG_VENTAS_LOYVERSE"
URL_BASE = "https://api.loyverse.com/v1.0"
COLUMNAS_VENTAS = [
    "Fecha", "Hora", "Numero_Recibo", "ID_Plato", "Nombre_Plato", 
    "Cantidad_Vendida", "Total_Dinero", "Metodo_Pago_Loyverse", 
    "Metodo_Pago_Real_Auditado", "Shift_ID"
]

# Token de seguridad
try:
    LOYVERSE_TOKEN = st.secrets["LOYVERSE_TOKEN"]
except:
    LOYVERSE_TOKEN = "2af9f2845c0b4417925d357b63cfab86"

HEADERS_API = {"Authorization": f"Bearer {LOYVERSE_TOKEN}"}

# --- FUNCIONES DE BASE DE DATOS ---

def asegurar_estructura_db(ws):
    try:
        actual_headers = ws.row_values(1)
        if not actual_headers or actual_headers != COLUMNAS_VENTAS:
            ws.clear()
            ws.update('A1', [COLUMNAS_VENTAS])
    except: pass

def obtener_shifts_descargados(sheet):
    try:
        ws = sheet.worksheet(NOMBRE_HOJA)
        df = leer_datos_seguro(ws)
        if not df.empty and "Shift_ID" in df.columns:
            return set(df["Shift_ID"].unique().tolist())
    except: pass
    return set()

# --- FUNCIONES API LOYVERSE ---

def obtener_turnos_rango(fecha_inicio, fecha_fin):
    url = f"{URL_BASE}/shifts"
    params = {
        "created_at_min": fecha_inicio.strftime("%Y-%m-%dT00:00:00Z"),
        "created_at_max": fecha_fin.strftime("%Y-%m-%dT23:59:59Z"),
        "limit": 250
    }
    turnos_encontrados = []
    cursor = None
    try:
        while True:
            if cursor: params["cursor"] = cursor
            r = requests.get(url, headers=HEADERS_API, params=params)
            if r.status_code != 200: break
            data = r.json()
            turnos_encontrados.extend(data.get("shifts", []))
            cursor = data.get("cursor")
            if not cursor: break
        return turnos_encontrados
    except: return []

def descargar_recibos_turno(opened_at, closed_at):
    url = f"{URL_BASE}/receipts"
    params = {
        "created_at_min": opened_at,
        "created_at_max": closed_at if closed_at else datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "limit": 250
    }
    try:
        r = requests.get(url, headers=HEADERS_API, params=params)
        return r.json().get("receipts", []) if r.status_code == 200 else []
    except: return []

def transformar_a_filas(recibos, shift_id):
    filas = []
    for r in recibos:
        dt_local = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")).astimezone(ZONA_HORARIA)
        pagos = r.get("payments", [])
        metodo = pagos[0].get("name", "Efectivo") if pagos else "Efectivo"
        for item in r.get("line_items", []):
            nombre = item.get("item_name", "Desconocido")
            if item.get("variant_name"): nombre += f" {item['variant_name']}"
            filas.append([
                dt_local.strftime("%Y-%m-%d"), dt_local.strftime("%H:%M"),
                r.get("receipt_number", "S/N"), item.get("item_id", ""),
                nombre, item.get("quantity", 1), item.get("total_money", 0),
                metodo, metodo, shift_id
            ])
    return filas

# --- INTERFAZ PRINCIPAL ---

def show(sheet):
    st.title("📈 Sincronización de Ventas")
    st.caption("Control de cierres por mes o rango personalizado.")
    
    if not sheet: return
    ws = sheet.worksheet(NOMBRE_HOJA)
    asegurar_estructura_db(ws)

    # --- 1. FILTRO DE BÚSQUEDA (CORREGIDO) ---
    with st.container(border=True):
        st.subheader("🔍 Filtro de Búsqueda")
        c1, c2, c3 = st.columns([1, 1, 1])
        
        modo_busqueda = c1.radio("Modo:", ["Por Mes", "Rango Libre"], horizontal=True)
        hoy = date.today()
        
        if modo_busqueda == "Por Mes":
            mes_sel = c2.selectbox("Mes:", list(range(1, 13)), 
                                   format_func=lambda x: calendar.month_name[x].capitalize(),
                                   index=hoy.month - 1)
            anio_sel = c3.selectbox("Año:", [2024, 2025, 2026], index=1)
            f_inicio = date(anio_sel, mes_sel, 1)
            f_fin = date(anio_sel, mes_sel, calendar.monthrange(anio_sel, mes_sel)[1])
        else:
            rango_custom = c2.date_input("Selecciona Rango:", [hoy - timedelta(days=7), hoy])
            if len(rango_custom) == 2:
                f_inicio, f_fin = rango_custom[0], rango_custom[1]
            else: f_inicio = f_fin = hoy

        if st.button("🚀 ESCANEAR CIERRES EN LOYVERSE", use_container_width=True, type="primary"):
            st.session_state["turnos_api"] = obtener_turnos_rango(f_inicio, f_fin)
            st.cache_data.clear()

    # --- 2. MOSTRAR RESULTADOS ---
    if "turnos_api" in st.session_state:
        turnos = st.session_state["turnos_api"]
        ids_descargados = obtener_shifts_descargados(sheet)

        if not turnos:
            st.info("No se encontraron cierres en el rango seleccionado.")
            return

        pendientes_para_bajar = []
        datos_tabla = []
        
        for s in turnos:
            id_s = s["id"]
            t_fin_raw = s.get("closed_at")
            descargado = id_s in ids_descargados
            
            if not t_fin_raw: estado = "🟢 ABIERTO"
            elif descargado: estado = "✅ DESCARGADO"
            else: 
                estado = "📥 PENDIENTE"
                pendientes_para_bajar.append(s)

            t_ini = datetime.fromisoformat(s["opened_at"].replace("Z", "+00:00")).astimezone(ZONA_HORARIA)
            t_fin = datetime.fromisoformat(t_fin_raw.replace("Z", "+00:00")).astimezone(ZONA_HORARIA) if t_fin_raw else None
            
            datos_tabla.append({
                "Estado": estado,
                "Fecha": t_ini.strftime("%d/%m/%Y"),
                "Inicio": t_ini.strftime("%I:%M %p"),
                "Fin": t_fin.strftime("%I:%M %p") if t_fin else "En curso",
                "Venta Bruta": f"$ {float(s.get('gross_sales', 0)):,.0f}",
                "ID": id_s
            })

        st.write("")
        st.subheader("📋 Resultados del Escaneo")
        st.dataframe(pd.DataFrame(datos_tabla)[["Estado", "Fecha", "Inicio", "Fin", "Venta Bruta"]], use_container_width=True, hide_index=True)

        # --- 3. ACCIONES DE DESCARGA ---
        if pendientes_para_bajar:
            st.markdown("---")
            st.warning(f"Se encontraron **{len(pendientes_para_bajar)}** cierres sin descargar.")
            
            if st.button("📥 DESCARGAR TODOS LOS PENDIENTES DEL RANGO", type="primary", use_container_width=True):
                progreso = st.progress(0)
                todas_las_filas = []
                
                for i, t in enumerate(pendientes_para_bajar):
                    recibos = descargar_recibos_turno(t["opened_at"], t["closed_at"])
                    if recibos:
                        todas_las_filas.extend(transformar_a_filas(recibos, t["id"]))
                    progreso.progress((i + 1) / len(pendientes_para_bajar))
                
                if todas_las_filas:
                    ws.append_rows(todas_las_filas)
                    st.success("Sincronización terminada.")
                    st.balloons()
                    time.sleep(2)
                    st.rerun()
        else:
            st.success("🎉 Todo está sincronizado para este periodo.")
