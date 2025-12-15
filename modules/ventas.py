import streamlit as st
import pandas as pd
import requests
import pytz
# Importamos time como dt_time para evitar conflictos de nombre
from datetime import datetime, timedelta, time as dt_time
import time 
# Importamos tus utilidades centrales
from utils import conectar_google_sheets, ZONA_HORARIA

# --- CONFIGURACIÓN ---
NOMBRE_HOJA = "LOG_VENTAS_LOYVERSE"
TOKEN_RESPALDO = "2af9f2845c0b4417925d357b63cfab86"

# Gestión de Secretos
try:
    LOYVERSE_TOKEN = st.secrets["LOYVERSE_TOKEN"]
except:
    LOYVERSE_TOKEN = TOKEN_RESPALDO

# --- FORMATO VISUAL ---
def formato_moneda_co(valor):
    """Formato visual: $ 50.000"""
    if pd.isna(valor) or valor == "": return "$ 0"
    try:
        return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return str(valor)

# --- BACKEND (LÓGICA) ---

def obtener_fechas_registradas(sheet):
    """Consulta fechas existentes para evitar duplicados"""
    if not sheet: return []
    try:
        ws = sheet.worksheet(NOMBRE_HOJA)
        fechas = ws.col_values(1)
        # Retornamos sin encabezado y únicos
        return list(set(fechas[1:])) if len(fechas) > 1 else []
    except: return []

def borrar_ventas_dia(sheet, fecha_str):
    """Borra un día específico para permitir re-descarga"""
    try:
        ws = sheet.worksheet(NOMBRE_HOJA)
        data = ws.get_all_records()
        if not data: return True
        
        df = pd.DataFrame(data)
        df["Fecha"] = df["Fecha"].astype(str)
        
        # Filtro inverso: Dejar lo que NO sea la fecha seleccionada
        df_limpio = df[df["Fecha"] != fecha_str]
        
        ws.clear()
        ws.update([df_limpio.columns.values.tolist()] + df_limpio.values.tolist())
        return True
    except Exception as e:
        st.error(f"Error al borrar: {e}")
        return False

def guardar_ventas(sheet, df_nuevos):
    """Escribe en Google Sheets respetando tu estructura exacta"""
    try:
        ws = sheet.worksheet(NOMBRE_HOJA)
        datos = df_nuevos.values.tolist()
        ws.append_rows(datos)
        return True
    except Exception as e:
        st.error(f"Error guardando en Sheets: {e}")
        return False

def descargar_de_api(fecha_obj):
    """Descarga de Loyverse, ajusta zona horaria y formatea datos"""
    url = "https://api.loyverse.com/v1.0/receipts"
    
    # Rango de tiempo exacto Colombia
    inicio_dia = datetime.combine(fecha_obj, dt_time.min).replace(tzinfo=ZONA_HORARIA)
    fin_dia = datetime.combine(fecha_obj, dt_time.max).replace(tzinfo=ZONA_HORARIA)
    
    params = {
        "created_at_min": inicio_dia.astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z'),
        "created_at_max": fin_dia.astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z'),
        "limit": 250
    }
    
    headers = {"Authorization": f"Bearer {LOYVERSE_TOKEN}"}
    ventas = []
    cursor = None
    
    while True:
        if cursor: params["cursor"] = cursor
        try:
            r = requests.get(url, headers=headers, params=params)
            if r.status_code != 200: break
            data = r.json()
        except: break
        
        receipts = data.get("receipts", [])
        
        for item in receipts:
            # Convertir UTC a Colombia
            try:
                fecha_col = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00")).astimezone(ZONA_HORARIA)
            except: continue
            
            # Filtro estricto de fecha local
            if fecha_col.date() == fecha_obj:
                pagos = item.get("payments", [])
                metodo = pagos[0].get("name", "Efectivo") if pagos else "Efectivo"
                
                # ESTRUCTURA EXACTA DE TU EXCEL (9 COLUMNAS)
                venta = {
                    "Fecha": fecha_col.strftime("%Y-%m-%d"),
                    "Hora": fecha_col.strftime("%H:%M"),
                    "Numero_Recibo": item.get("receipt_number", "S/N"),
                    "ID_Plato": "TICKET", 
                    "Nombre_Plato": "Venta POS",
                    "Cantidad_Vendida": 1,
                    "Total_Dinero": item.get("total_money", 0),
                    "Metodo_Pago_Loyverse": metodo,
                    "Metodo_Pago_Real_Auditado": metodo
                }
                ventas.append(venta)
            
        cursor = data.get("cursor")
        if not cursor: break
    
    # Convertir a DataFrame y CORREGIR TIPOS DE DATOS (El arreglo del error PyArrow)
    df = pd.DataFrame(ventas)
    
    if not df.empty:
        # Forzamos estas columnas a texto para que Streamlit no se confunda
        df["ID_Plato"] = df["ID_Plato"].astype(str)
        df["Numero_Recibo"] = df["Numero_Recibo"].astype(str)
        
    return df

# --- FRONTEND (INTERFAZ) ---

def show(sheet):
    st.title("💰 Módulo de Ventas V7")
    st.markdown("---")
    
    # 1. Selector
    col_date, _ = st.columns([1, 2])
    with col_date:
        fecha_selec = st.date_input("📅 Fecha de Cierre", value=datetime.now(ZONA_HORARIA).date())
        fecha_str = fecha_selec.strftime("%Y-%m-%d")

    # 2. Verificar si ya existe
    fechas_existentes = obtener_fechas_registradas(sheet)
    
    if fecha_str in fechas_existentes:
        # ESTADO: BLOQUEADO
        st.warning(f"⚠️ Las ventas del **{fecha_str}** ya están registradas.")
        st.info("Para volver a descargar, primero debes borrar el registro existente.")
        
        if st.button("🗑️ Borrar y Re-descargar", type="primary"):
            with st.spinner("Eliminando registros..."):
                if borrar_ventas_dia(sheet, fecha_str):
                    st.success("Borrado exitoso. Recargando...")
                    time.sleep(1)
                    st.rerun()
    else:
        # ESTADO: LISTO
        st.success(f"✅ Fecha {fecha_str} disponible.")
        
        if st.button("📥 Descargar de Loyverse", use_container_width=True):
            with st.spinner("Conectando con API Loyverse..."):
                df = descargar_de_api(fecha_selec)
                
            if df is not None and not df.empty:
                # Métricas
                total = df["Total_Dinero"].sum()
                st.metric("VENTA TOTAL", formato_moneda_co(total))
                
                # Vista Previa
                st.subheader("📊 Vista Previa")
                df_view = df.copy()
                df_view["Total_Dinero"] = df_view["Total_Dinero"].apply(formato_moneda_co)
                st.dataframe(df_view, use_container_width=True, hide_index=True)
                
                # Guardar
                with st.status("Guardando en Base de Datos...", expanded=True) as status:
                    if guardar_ventas(sheet, df):
                        status.update(label="¡Guardado Exitoso!", state="complete", expanded=False)
                        st.balloons()
                        time.sleep(2)
                        st.rerun()
                    else:
                        status.update(label="Error al guardar", state="error")
            else:
                st.info("Loyverse no reporta ventas para este día.")

    # 3. Auditoría
    st.markdown("---")
    with st.expander("🔍 Ver últimos registros en BD"):
        try:
            ws = sheet.worksheet(NOMBRE_HOJA)
            data = ws.get_all_records()
            if data:
                df_log = pd.DataFrame(data).tail(5)
                if "Total_Dinero" in df_log.columns:
                    df_log["Total_Dinero"] = pd.to_numeric(df_log["Total_Dinero"], errors='coerce').apply(formato_moneda_co)
                st.table(df_log)
        except: pass