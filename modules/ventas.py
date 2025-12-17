import streamlit as st
import pandas as pd
import requests
import pytz
from datetime import datetime, timedelta, time as dt_time
import time 
from utils import conectar_google_sheets, ZONA_HORARIA

# --- CONFIGURACIÓN ---
NOMBRE_HOJA = "LOG_VENTAS_LOYVERSE"
TOKEN_RESPALDO = "2af9f2845c0b4417925d357b63cfab86"

try:
    LOYVERSE_TOKEN = st.secrets["LOYVERSE_TOKEN"]
except:
    LOYVERSE_TOKEN = TOKEN_RESPALDO

def formato_moneda_co(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try:
        return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return str(valor)

# --- FUNCIÓN ANTI-BLOQUEO (RETRY LOGIC) ---
def ejecutar_con_reintento(func, *args):
    """Intenta ejecutar una función de Google Sheets hasta 3 veces si sale error 429"""
    intentos = 3
    for i in range(intentos):
        try:
            return func(*args)
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "Quota exceeded" in error_str:
                if i < intentos - 1: # Si no es el último intento
                    tiempo_espera = (i + 1) * 5 # Espera 5s, luego 10s...
                    st.toast(f"⏳ Google está ocupado. Reintentando en {tiempo_espera}s...", icon="🐢")
                    time.sleep(tiempo_espera)
                    continue
            # Si es otro error o se acabaron los intentos, fallar
            st.error(f"Error de conexión: {e}")
            return None
    return None

# --- BACKEND ---

def _obtener_fechas_core(sheet):
    ws = sheet.worksheet(NOMBRE_HOJA)
    fechas = ws.col_values(1)
    return list(set(fechas[1:])) if len(fechas) > 1 else []

def obtener_fechas_registradas(sheet):
    if not sheet: return []
    # Usamos el wrapper de reintento
    return ejecutar_con_reintento(_obtener_fechas_core, sheet) or []

def borrar_ventas_dia(sheet, fecha_str):
    def _borrar_core():
        ws = sheet.worksheet(NOMBRE_HOJA)
        data = ws.get_all_records()
        if not data: return True
        df = pd.DataFrame(data)
        df["Fecha"] = df["Fecha"].astype(str)
        df_limpio = df[df["Fecha"] != fecha_str]
        ws.clear()
        ws.update([df_limpio.columns.values.tolist()] + df_limpio.values.tolist())
        return True
    
    return ejecutar_con_reintento(_borrar_core)

def guardar_ventas(sheet, df_nuevos):
    def _guardar_core():
        ws = sheet.worksheet(NOMBRE_HOJA)
        datos = df_nuevos.values.tolist()
        ws.append_rows(datos)
        return True
        
    return ejecutar_con_reintento(_guardar_core)

def descargar_de_api(fecha_obj):
    url = "https://api.loyverse.com/v1.0/receipts"
    
    inicio_dia = datetime.combine(fecha_obj, dt_time.min).replace(tzinfo=ZONA_HORARIA)
    fin_dia = datetime.combine(fecha_obj, dt_time.max).replace(tzinfo=ZONA_HORARIA)
    
    params = {
        "created_at_min": inicio_dia.astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z'),
        "created_at_max": fin_dia.astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z'),
        "limit": 250
    }
    
    headers = {"Authorization": f"Bearer {LOYVERSE_TOKEN}"}
    ventas_detalle = []
    cursor = None
    
    # Placeholder sin molestar a Google
    placeholder = st.empty()
    placeholder.info("⏳ Consultando Loyverse...")
    
    while True:
        if cursor: params["cursor"] = cursor
        try:
            r = requests.get(url, headers=headers, params=params)
            if r.status_code != 200: break
            data = r.json()
        except: break
        
        receipts = data.get("receipts", [])
        
        for r in receipts:
            try:
                fecha_col = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")).astimezone(ZONA_HORARIA)
            except: continue
            
            if fecha_col.date() != fecha_obj: continue

            hora = fecha_col.strftime("%H:%M")
            recibo_no = r.get("receipt_number", "S/N")
            pagos = r.get("payments", [])
            metodo = pagos[0].get("name", "Efectivo") if pagos else "Efectivo"
            
            items = r.get("line_items", [])
            
            if not items:
                venta = {
                    "Fecha": fecha_col.strftime("%Y-%m-%d"), "Hora": hora, "Numero_Recibo": recibo_no,
                    "ID_Plato": "MANUAL", "Nombre_Plato": "Venta Manual", "Cantidad_Vendida": 1,
                    "Total_Dinero": r.get("total_money", 0),
                    "Metodo_Pago_Loyverse": metodo, "Metodo_Pago_Real_Auditado": metodo
                }
                ventas_detalle.append(venta)
            else:
                for item in items:
                    nombre_plato = item.get("item_name", "Desconocido")
                    if item.get("variant_name"): 
                        nombre_plato = f"{nombre_plato} {item.get('variant_name')}".strip()
                    
                    cantidad = item.get("quantity", 1)
                    dinero_linea = item.get("total_money", 0)
                    
                    # FILAS
                    fila = [
                        fecha_col.strftime("%Y-%m-%d"), 
                        hora,                           
                        str(recibo_no),                 
                        str(item.get("item_id", "")),   
                        nombre_plato,                   
                        cantidad,                       
                        dinero_linea,                   
                        metodo,                         
                        metodo                          
                    ]
                    ventas_detalle.append(fila)
            
        cursor = data.get("cursor")
        if not cursor: break
    
    placeholder.empty()
    
    columnas = [
        "Fecha", "Hora", "Numero_Recibo", "ID_Plato", 
        "Nombre_Plato", "Cantidad_Vendida", "Total_Dinero", 
        "Metodo_Pago_Loyverse", "Metodo_Pago_Real_Auditado"
    ]
    df = pd.DataFrame(ventas_detalle, columns=columnas)
    
    return df

# --- FRONTEND ---

def show(sheet):
    st.title("💰 Ventas V7 (Anti-Bloqueo)")
    st.markdown("---")
    
    hoy_co = datetime.now(ZONA_HORARIA).date()
    col1, _ = st.columns([1, 2])
    fecha_selec = col1.date_input("Fecha de Cierre", value=hoy_co)
    fecha_str = fecha_selec.strftime("%Y-%m-%d")

    fechas_existentes = obtener_fechas_registradas(sheet)
    
    if fecha_str in fechas_existentes:
        st.warning(f"⚠️ El día {fecha_str} ya tiene datos descargados.")
        
        if st.button("🗑️ Borrar y Re-descargar Ahora", type="primary"):
            with st.spinner("Borrando... (Si demora, es Google pensando)"):
                if borrar_ventas_dia(sheet, fecha_str):
                    st.success("✅ Borrado. Recargando...")
                    time.sleep(2)
                    st.rerun()
    else:
        # Botón de descarga
        if st.button("📥 Descargar Ventas Detalladas", use_container_width=True):
            with st.spinner("Conectando con Loyverse..."):
                df = descargar_de_api(fecha_selec)
                
            if df is not None and not df.empty:
                total = df["Total_Dinero"].sum()
                st.metric("Venta Total", formato_moneda_co(total))
                st.dataframe(df[["Hora", "Nombre_Plato", "Cantidad_Vendida"]], use_container_width=True)
                
                with st.status("Guardando... (Paciencia, evitando errores)", expanded=True):
                    if guardar_ventas(sheet, df):
                        st.write("✅ ¡Guardado Exitoso!")
                        time.sleep(1)
                        st.rerun()
            else:
                st.info("No se encontraron ventas.")

    st.markdown("---")
    # Auditoría solo bajo demanda para ahorrar cuota
    if st.checkbox("🔍 Ver últimos registros guardados (Consume cuota Google)"):
        def _leer_audit():
            ws = sheet.worksheet(NOMBRE_HOJA)
            return pd.DataFrame(ws.get_all_records()).tail(5)
        
        df_log = ejecutar_con_reintento(_leer_audit)
        if df_log is not None:
            st.table(df_log)