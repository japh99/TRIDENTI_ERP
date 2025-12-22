import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
import pytz
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

# --- FUNCIONES DE BASE DE DATOS (AUTO-ORGANIZADA) ---

def asegurar_estructura_db(ws):
    """Verifica y crea los encabezados correctos si no existen."""
    try:
        actual_headers = ws.row_values(1)
        if not actual_headers or actual_headers != COLUMNAS_VENTAS:
            ws.clear()
            ws.update('A1', [COLUMNAS_VENTAS])
            st.toast("Base de datos organizada automáticamente.", icon="⚙️")
    except: pass

def obtener_ids_descargados(sheet):
    """Busca en el Excel qué turnos ya fueron procesados."""
    try:
        ws = sheet.worksheet(NOMBRE_HOJA)
        df = leer_datos_seguro(ws)
        if not df.empty and "Shift_ID" in df.columns:
            return df["Shift_ID"].unique().tolist()
    except: pass
    return []

# --- FUNCIONES API LOYVERSE ---

def api_get(endpoint, params=None):
    """Función genérica para peticiones a Loyverse con manejo de errores."""
    try:
        r = requests.get(f"{URL_BASE}/{endpoint}", headers=HEADERS_API, params=params)
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 429:
            st.error("Límite de API Loyverse alcanzado. Espera 1 minuto.")
        else:
            st.error(f"Error Loyverse: {r.status_code}")
        return None
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None

def descargar_recibos_turno(opened_at, closed_at):
    """Baja todos los recibos de un turno específico."""
    params = {
        "created_at_min": opened_at,
        "created_at_max": closed_at,
        "limit": 250
    }
    data = api_get("receipts", params)
    return data.get("receipts", []) if data else []

# --- PROCESAMIENTO ---

def transformar_datos(recibos, shift_id):
    """Convierte el JSON de la API a una lista para el Excel."""
    filas = []
    for r in recibos:
        # Convertir UTC a Hora Local Colombia
        dt_utc = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
        dt_local = dt_utc.astimezone(ZONA_HORARIA)
        
        pagos = r.get("payments", [])
        metodo = pagos[0].get("name", "Efectivo") if pagos else "Efectivo"
        
        for item in r.get("line_items", []):
            nombre = item.get("item_name", "Desconocido")
            if item.get("variant_name"): nombre += f" {item['variant_name']}"
            
            filas.append([
                dt_local.strftime("%Y-%m-%d"),
                dt_local.strftime("%H:%M"),
                r.get("receipt_number", "S/N"),
                item.get("item_id", ""),
                nombre,
                item.get("quantity", 1),
                item.get("total_money", 0),
                metodo, # Loyverse
                metodo, # Auditado (inicialmente igual)
                shift_id
            ])
    return filas

# --- INTERFAZ PRINCIPAL ---

def show(sheet):
    st.title("📈 Sincronización de Ventas Pro")
    st.caption("Conexión directa con los cierres de Loyverse (Shifts).")
    
    if not sheet: return
    ws = sheet.worksheet(NOMBRE_HOJA)
    asegurar_structure_db = asegurar_estructura_db(ws)

    # 1. CARGAR DATOS
    with st.spinner("Sincronizando con la nube de Loyverse..."):
        ids_viejos = obtener_ids_descargados(sheet)
        data_shifts = api_get("shifts", {"limit": 15}) # Traer los últimos 15 turnos

    if not data_shifts:
        st.warning("No se pudieron recuperar cierres. Verifica tu conexión o el Token de Loyverse.")
        return

    # 2. MOSTRAR TABLA DE TURNOS
    st.subheader("🏪 Historial de Turnos en Loyverse")
    
    lista_turnos = []
    for s in data_shifts.get("shifts", []):
        id_s = s["id"]
        t_ini = datetime.fromisoformat(s["opened_at"].replace("Z", "+00:00")).astimezone(ZONA_HORARIA)
        
        t_fin_raw = s.get("closed_at")
        descargado = id_s in ids_viejos
        
        # Lógica de estado
        if not t_fin_raw:
            estado = "🟢 ABIERTO (No descargar)"
            color = "gray"
        elif descargado:
            estado = "✅ DESCARGADO"
            color = "green"
        else:
            estado = "📥 PENDIENTE"
            color = "orange"

        t_fin = datetime.fromisoformat(t_fin_raw.replace("Z", "+00:00")).astimezone(ZONA_HORARIA) if t_fin_raw else None
        
        lista_turnos.append({
            "Estado": estado,
            "Inicio": t_ini.strftime("%d/%m %I:%M %p"),
            "Fin": t_fin.strftime("%d/%m %I:%M %p") if t_fin else "En curso...",
            "Venta Bruta": f"$ {float(s.get('gross_sales', 0)):,.0f}",
            "id": id_s,
            "raw_open": s["opened_at"],
            "raw_close": t_fin_raw
        })

    df_ui = pd.DataFrame(lista_turnos)
    st.dataframe(df_ui[["Estado", "Inicio", "Fin", "Venta Bruta"]], use_container_width=True, hide_index=True)

    # 3. ACCIÓN DE DESCARGA
    st.markdown("---")
    
    # Filtrar solo los que realmente se pueden descargar
    pendientes = df_ui[df_ui["Estado"] == "📥 PENDIENTE"].copy()

    if not pendientes.empty:
        col1, col2 = st.columns([2, 1])
        seleccion = col1.selectbox("Selecciona un turno para bajar al sistema:", pendientes["Inicio"].tolist())
        
        if col2.button("🚀 DESCARGAR AHORA", type="primary", use_container_width=True):
            # Obtener datos del turno elegido
            turno_obj = pendientes[pendientes["Inicio"] == seleccion].iloc[0]
            
            with st.status(f"Descargando turno {seleccion}...", expanded=True) as status:
                recibos = descargar_recibos_turno(turno_obj["raw_open"], turno_obj["raw_close"])
                
                if recibos:
                    st.write("✅ Recibos obtenidos. Procesando...")
                    filas_finales = transformar_datos(recibos, turno_obj["id"])
                    
                    # Subir a Google Sheets
                    ws.append_rows(filas_finales)
                    
                    status.update(label="Sincronización Exitosa", state="complete")
                    st.success(f"Se integraron {len(filas_finales)} registros de venta.")
                    st.balloons()
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error("No se encontraron recibos en este turno.")
    else:
        st.success("🎉 Todo el historial de cierres está al día.")

    # Botones inferiores
    st.markdown("---")
    c_inf1, c_inf2 = st.columns(2)
    if c_inf1.button("🔄 ACTUALIZAR LISTA"):
        st.cache_data.clear()
        st.rerun()
        
    with c_inf2.expander("🗑️ Zona de Peligro"):
        if st.button("BORRAR TODO EL HISTORIAL DE VENTAS"):
            ws.clear()
            ws.update('A1', [COLUMNAS_VENTAS])
            st.cache_data.clear()
            st.error("Historial eliminado.")
            st.rerun()
