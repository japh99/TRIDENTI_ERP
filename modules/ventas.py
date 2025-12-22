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
    """Consulta la lista de cierres (shifts) en Loyverse."""
    url = f"{URL_BASE}/shifts"
    # Rango amplio para capturar cierres que cruzan medianoche
    min_t = datetime.combine(fecha_obj, datetime.min.time()) - timedelta(hours=12)
    max_t = datetime.combine(fecha_obj, datetime.max.time()) + timedelta(hours=24)
    
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
    """Descarga todos los recibos emitidos durante el turno."""
    url = f"{URL_BASE}/receipts"
    params = {
        "created_at_min": opened_at,
        "created_at_max": closed_at if closed_at else datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "limit": 250
    }
    
    try:
        r = requests.get(url, headers=HEADERS_API, params=params)
        if r.status_code == 200:
            return r.json().get("receipts", [])
        return []
    except: return []

# --- LÓGICA DE CONTROL DE DUPLICADOS ---

def verificar_descarga_en_sheet(sheet, opened_at, closed_at):
    """Revisa si ya existen ventas en el rango de tiempo del turno en el Excel."""
    try:
        ws = sheet.worksheet(NOMBRE_HOJA)
        df_existente = leer_datos_seguro(ws)
        if df_existente.empty: return False
        
        # Combinar Fecha y Hora del Excel para comparar
        df_existente["TS"] = pd.to_datetime(df_existente["Fecha"] + " " + df_existente["Hora"])
        
        # Convertir tiempos de la API a datetime
        start = pd.to_datetime(opened_at).tz_convert(None)
        # Si el turno sigue abierto, usamos ahora
        end = pd.to_datetime(closed_at).tz_convert(None) if closed_at else datetime.utcnow()
        
        # Si hay algun registro en ese rango, lo marcamos como descargado
        coincidencias = df_existente[(df_existente["TS"] >= start) & (df_existente["TS"] <= end)]
        return len(coincidencias) > 0
    except: return False

def procesar_recibos_a_df(recibos):
    """Convierte la respuesta JSON de Loyverse en un DataFrame limpio."""
    filas = []
    for r in recibos:
        # Convertir hora UTC a Colombia
        fecha_dt = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")).astimezone(ZONA_HORARIA)
        fecha_str = fecha_dt.strftime("%Y-%m-%d")
        hora_str = fecha_dt.strftime("%H:%M")
        recibo_no = r.get("receipt_number", "S/N")
        
        pagos = r.get("payments", [])
        metodo = pagos[0].get("name", "Efectivo") if pagos else "Efectivo"
        
        items = r.get("line_items", [])
        for it in items:
            nombre = it.get("item_name", "Desconocido")
            if it.get("variant_name"): nombre = f"{nombre} {it['variant_name']}"
            
            filas.append([
                fecha_str, 
                hora_str, 
                recibo_no, 
                it.get("item_id", ""),
                nombre, 
                it.get("quantity", 1), 
                it.get("total_money", 0),
                metodo, # Metodo_Pago_Loyverse
                metodo  # Metodo_Pago_Real_Auditado (Inicializado igual)
            ])
    
    columnas = ["Fecha", "Hora", "Numero_Recibo", "ID_Plato", "Nombre_Plato", "Cantidad_Vendida", "Total_Dinero", "Metodo_Pago_Loyverse", "Metodo_Pago_Real_Auditado"]
    return pd.DataFrame(filas, columns=columnas)

# --- INTERFAZ ---

def show(sheet):
    st.title("📈 Sincronización de Ventas por Cierres")
    st.caption("Evita duplicados descargando turnos específicos de Loyverse.")
    
    if not sheet: return

    # 1. Búsqueda de Turnos
    hoy = datetime.now(ZONA_HORARIA).date()
    col_f1, col_f2 = st.columns([1, 2])
    fecha_busqueda = col_f1.date_input("¿Qué día abrió caja?", value=hoy)
    
    with st.spinner("Buscando cierres en Loyverse..."):
        turnos = obtener_turnos_api(fecha_busqueda)
    
    if not turnos:
        st.warning(f"No se detectaron cierres el día {fecha_busqueda}.")
        return

    # 2. Identificar cuáles ya están en el sistema
    opciones_turnos = []
    estados_descarga = []
    
    for i, t in enumerate(turnos):
        t_open = datetime.fromisoformat(t["opened_at"].replace("Z", "+00:00")).astimezone(ZONA_HORARIA)
        t_close_raw = t.get("closed_at")
        t_close = datetime.fromisoformat(t_close_raw.replace("Z", "+00:00")).astimezone(ZONA_HORARIA) if t_close_raw else None
        
        # Verificar en el Excel
        ya_descargado = verificar_descarga_en_sheet(sheet, t["opened_at"], t_close_raw)
        icon = "✅ (Ya en Sistema)" if ya_descargado else "📥 (Pendiente)"
        
        label = f"{icon} Cierre: {t_open.strftime('%H:%M')} a {t_close.strftime('%H:%M') if t_close else 'Abierto'}"
        opciones_turnos.append(label)
        estados_descarga.append(ya_descargado)

    # 3. Selector de Turno
    st.markdown("### 🏪 Turnos Disponibles")
    seleccion = st.selectbox("Selecciona el turno para procesar:", opciones_turnos)
    idx_sel = opciones_turnos.index(seleccion)
    turno_final = turnos[idx_sel]
    esta_listo = estados_descarga[idx_sel]

    st.markdown("---")
    c1, c2 = st.columns(2)

    if esta_listo:
        c1.info("Este turno ya fue descargado previamente.")
        if c1.button("♻️ VOLVER A DESCARGAR (Sobrescribir)", use_container_width=True):
            esta_listo = False # Forzamos la descarga

    if not esta_listo:
        if c1.button("🚀 DESCARGAR VENTAS AHORA", type="primary", use_container_width=True):
            with st.status("Conectando con Loyverse...", expanded=True) as status:
                recibos = descargar_recibos_turno(turno_final["opened_at"], turno_final.get("closed_at"))
                
                if recibos:
                    df_nuevos = procesar_recibos_a_df(recibos)
                    ws = sheet.worksheet(NOMBRE_HOJA)
                    
                    # Guardar
                    ws.append_rows(df_nuevos.values.tolist())
                    
                    status.update(label="Sincronización Exitosa", state="complete")
                    st.success(f"Se guardaron {len(recibos)} recibos correctamente.")
                    st.balloons()
                    time.sleep(2)
                    st.rerun()
                else:
                    status.update(label="Error", state="error")
                    st.error("No hay ventas en este turno.")

    if c2.button("🔄 ACTUALIZAR LISTA", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
