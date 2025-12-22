import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from utils import conectar_google_sheets, ZONA_HORARIA, leer_datos_seguro

# --- CONFIGURACIÓN ---
NOMBRE_HOJA = "LOG_VENTAS_LOYVERSE"
URL_BASE = "https://api.loyverse.com/v1.0"

# Intentar obtener token de secrets
try:
    LOYVERSE_TOKEN = st.secrets["LOYVERSE_TOKEN"]
except:
    LOYVERSE_TOKEN = "2af9f2845c0b4417925d357b63cfab86"

HEADERS_API = {"Authorization": f"Bearer {LOYVERSE_TOKEN}"}

# --- FUNCIONES API LOYVERSE ---

def obtener_turnos_api(fecha_obj):
    """Consulta la lista de cierres (shifts) de un día específico."""
    url = f"{URL_BASE}/shifts"
    # Buscamos un rango amplio alrededor del día para no perder los de la madrugada
    min_t = datetime.combine(fecha_obj, datetime.min.time()) - timedelta(hours=12)
    max_t = datetime.combine(fecha_obj, datetime.max.time()) + timedelta(hours=12)
    
    params = {
        "created_at_min": min_t.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "created_at_max": max_t.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "limit": 50
    }
    
    try:
        r = requests.get(url, headers=HEADERS_API, params=params)
        if r.status_code == 200:
            return r.json().get("shifts", [])
        return []
    except: return []

def descargar_recibos_turno(opened_at, closed_at):
    """Descarga todos los recibos entre la apertura y cierre del turno."""
    url = f"{URL_BASE}/receipts"
    # Ajustamos un margen de 1 minuto para asegurar que entren todos
    params = {
        "created_at_min": opened_at,
        "created_at_max": closed_at if closed_at else datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "limit": 250
    }
    
    recibos_totales = []
    try:
        r = requests.get(url, headers=HEADERS_API, params=params)
        if r.status_code == 200:
            recibos_totales = r.json().get("receipts", [])
    except: pass
    return recibos_totales

# --- PROCESAMIENTO DE DATOS ---

def procesar_recibos_a_df(recibos):
    filas = []
    for r in recibos:
        fecha_dt = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")).astimezone(ZONA_HORARIA)
        fecha_str = fecha_dt.strftime("%Y-%m-%d")
        hora_str = fecha_dt.strftime("%H:%M")
        recibo_no = r.get("receipt_number", "S/N")
        
        pagos = r.get("payments", [])
        metodo = pagos[0].get("name", "Efectivo") if pagos else "Efectivo"
        
        items = r.get("line_items", [])
        if not items:
            filas.append([fecha_str, hora_str, recibo_no, "MANUAL", "Venta Manual", 1, r.get("total_money", 0), metodo, metodo])
        else:
            for it in items:
                nombre = it.get("item_name", "Desconocido")
                if it.get("variant_name"): nombre = f"{nombre} {it['variant_name']}"
                filas.append([
                    fecha_str, hora_str, recibo_no, it.get("item_id", ""),
                    nombre, it.get("quantity", 1), it.get("total_money", 0),
                    metodo, metodo
                ])
    
    columnas = ["Fecha", "Hora", "Numero_Recibo", "ID_Plato", "Nombre_Plato", "Cantidad_Vendida", "Total_Dinero", "Metodo_Pago_Loyverse", "Metodo_Pago_Real_Auditado"]
    return pd.DataFrame(filas, columns=columnas)

# --- INTERFAZ ---

def show(sheet):
    st.title("📈 Descarga de Ventas por Cierres")
    st.caption("Sincroniza los turnos reales de Loyverse con tu base de datos.")
    
    if not sheet: return

    # 1. Seleccionar Fecha para buscar turnos
    hoy = datetime.now(ZONA_HORARIA).date()
    fecha_busqueda = st.date_input("¿De qué día quieres ver los cierres?", value=hoy)
    
    with st.spinner("Buscando turnos en Loyverse..."):
        turnos = obtener_turnos_api(fecha_busqueda)
    
    if not turnos:
        st.warning("No se encontraron cierres (shifts) en Loyverse para esta fecha.")
        if st.button("🔄 Reintentar"): st.rerun()
        return

    # 2. Elegir el Turno específico
    st.markdown("### 🏪 Cierres encontrados en Loyverse")
    
    opciones_turnos = []
    for i, t in enumerate(turnos):
        f_open = datetime.fromisoformat(t["opened_at"].replace("Z", "+00:00")).astimezone(ZONA_HORARIA).strftime("%H:%M")
        f_close = "Abierto"
        if t.get("closed_at"):
            f_close = datetime.fromisoformat(t["closed_at"].replace("Z", "+00:00")).astimezone(ZONA_HORARIA).strftime("%H:%M")
        
        opciones_turnos.append(f"Cierre #{len(turnos)-i} | Inicio: {f_open} - Fin: {f_close}")

    seleccion = st.selectbox("Selecciona el turno que vas a sincronizar:", opciones_turnos)
    idx_turno = opciones_turnos.index(seleccion)
    turno_data = turnos[idx_turno]

    # 3. Descargar y Guardar
    st.markdown("---")
    c1, c2 = st.columns(2)
    
    if c1.button("🚀 DESCARGAR Y SINCRONIZAR ESTE TURNO", type="primary", use_container_width=True):
        with st.status("Sincronizando con Loyverse...", expanded=True) as status:
            st.write("Bajando recibos...")
            recibos = descargar_recibos_turno(turno_data["opened_at"], turno_data.get("closed_at"))
            
            if recibos:
                df_nuevos = procesar_recibos_a_df(recibos)
                st.write(f"Procesados {len(recibos)} recibos...")
                
                # Guardar en Google Sheets
                ws = sheet.worksheet(NOMBRE_HOJA)
                # Opcional: Borrar si ya existen esos recibos para no duplicar
                # datos = df_nuevos.values.tolist()
                ws.append_rows(df_nuevos.values.tolist())
                
                status.update(label="✅ Sincronización Exitosa", state="complete")
                st.success(f"Turno guardado. Ahora puedes ir a Tesorería a auditar los tickets.")
                st.balloons()
            else:
                status.update(label="No hay recibos", state="error")
                st.error("Este turno no tiene ventas registradas.")

    if c2.button("🗑️ LIMPIAR HISTORIAL LOCAL", use_container_width=True):
        st.cache_data.clear()
        st.success("Memoria limpia.")
