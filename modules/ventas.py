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

# --- FUNCIONES API LOYVERSE (CON SOPORTE PARA MES COMPLETO) ---

def obtener_turnos_mes(anio, mes):
    """Trae todos los turnos de un mes específico usando paginación."""
    url = f"{URL_BASE}/shifts"
    
    # Rango del mes
    primer_dia = datetime(anio, mes, 1, 0, 0, 0)
    ultimo_dia = datetime(anio, mes, calendar.monthrange(anio, mes)[1], 23, 59, 59)
    
    params = {
        "created_at_min": primer_dia.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "created_at_max": ultimo_dia.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "limit": 250
    }
    
    todos_los_turnos = []
    cursor = None
    
    try:
        while True:
            if cursor: params["cursor"] = cursor
            r = requests.get(url, headers=HEADERS_API, params=params)
            if r.status_code != 200: break
            
            data = r.json()
            todos_los_turnos.extend(data.get("shifts", []))
            
            cursor = data.get("cursor")
            if not cursor: break
            
        return todos_los_turnos
    except:
        return []

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

# --- PROCESAMIENTO ---

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

# --- INTERFAZ ---

def show(sheet):
    st.title("📈 Sincronización de Ventas")
    st.caption("Filtra por mes para encontrar cierres pendientes de descargar.")
    
    if not sheet: return
    ws = sheet.worksheet(NOMBRE_HOJA)
    asegurar_estructura_db(ws)

    # 1. FILTROS DE BÚSQUEDA
    with st.sidebar:
        st.header("⚙️ Rango de Búsqueda")
        anio_sel = st.selectbox("Año:", [2024, 2025, 2026], index=1)
        mes_sel = st.selectbox("Mes:", list(range(1, 13)), 
                               format_func=lambda x: calendar.month_name[x].capitalize(),
                               index=datetime.now().month - 1)
        
        if st.button("🔄 ESCANEAR MES", use_container_width=True, type="primary"):
            st.cache_data.clear()
            st.rerun()

    # 2. CARGAR DATOS
    with st.spinner(f"Escaneando cierres de {calendar.month_name[mes_sel]}..."):
        shifts_api = obtener_turnos_mes(anio_sel, mes_sel)
        ids_descargados = obtener_shifts_descargados(sheet)

    if not shifts_api:
        st.info(f"No se encontraron cierres en {calendar.month_name[mes_sel]} {anio_sel}.")
        return

    # 3. CLASIFICAR TURNOS
    datos_tabla = []
    pendientes_lista = []

    for s in shifts_api:
        id_s = s["id"]
        t_ini = datetime.fromisoformat(s["opened_at"].replace("Z", "+00:00")).astimezone(ZONA_HORARIA)
        t_fin_raw = s.get("closed_at")
        
        descargado = id_s in ids_descargados
        es_abierto = not t_fin_raw
        
        if es_abierto:
            estado = "🟢 ABIERTO"
        elif descargado:
            estado = "✅ DESCARGADO"
        else:
            estado = "📥 PENDIENTE"
            pendientes_lista.append(s)

        t_fin = datetime.fromisoformat(t_fin_raw.replace("Z", "+00:00")).astimezone(ZONA_HORARIA) if t_fin_raw else None
        
        datos_tabla.append({
            "Estado": estado,
            "Fecha": t_ini.strftime("%d/%m/%Y"),
            "Hora Inicio": t_ini.strftime("%I:%M %p"),
            "Hora Fin": t_fin.strftime("%I:%M %p") if t_fin else "En curso",
            "Venta Bruta": f"$ {float(s.get('gross_sales', 0)):,.0f}",
            "ID": id_s
        })

    df_ui = pd.DataFrame(datos_tabla)
    
    # Mostrar Resumen
    st.subheader(f"Cierres en {calendar.month_name[mes_sel]} {anio_sel}")
    st.dataframe(df_ui, use_container_width=True, hide_index=True)

    # 4. ACCIONES MASIVAS O INDIVIDUALES
    st.markdown("---")
    
    if pendientes_lista:
        st.warning(f"Se encontraron **{len(pendientes_lista)}** cierres pendientes por bajar.")
        
        col1, col2 = st.columns(2)
        
        # Opción 1: Descargar uno específico
        with col1:
            opciones_p = [f"{datetime.fromisoformat(p['opened_at'].replace('Z','+00:00')).astimezone(ZONA_HORARIA).strftime('%d/%m %I:%M %p')} - {p['id'][:6]}" for p in pendientes_lista]
            sel_uno = st.selectbox("Descargar uno solo:", opciones_p)
            
            if st.button("📥 BAJAR SELECCIONADO"):
                turno_p = pendientes_lista[opciones_p.index(sel_uno)]
                with st.status("Bajando recibos..."):
                    recibos = descargar_recibos_turno(turno_p["opened_at"], turno_p["closed_at"])
                    if recibos:
                        filas = transformar_a_filas(recibos, turno_p["id"])
                        ws.append_rows(filas)
                        st.success("Descarga exitosa.")
                        time.sleep(1); st.rerun()

        # Opción 2: Descargar todo el mes pendiente
        with col2:
            st.write("¿Quieres bajar todo de una vez?")
            if st.button("🚀 DESCARGAR TODO LO PENDIENTE", type="primary"):
                total_filas = 0
                progreso = st.progress(0)
                status_masivo = st.empty()
                
                todas_las_filas = []
                for i, turno_p in enumerate(pendientes_lista):
                    status_masivo.write(f"Procesando cierre {i+1} de {len(pendientes_lista)}...")
                    recibos = descargar_recibos_turno(turno_p["opened_at"], turno_p["closed_at"])
                    if recibos:
                        todas_las_filas.extend(transformar_a_filas(recibos, turno_p["id"]))
                    progreso.progress((i + 1) / len(pendientes_lista))
                
                if todas_las_filas:
                    st.write(f"Subiendo {len(todas_las_filas)} registros a Google Sheets...")
                    ws.append_rows(todas_las_filas)
                    st.success(f"¡Listo! Se sincronizaron {len(pendientes_lista)} cierres.")
                    st.balloons()
                    time.sleep(2); st.rerun()
    else:
        st.success("✅ Todo este mes está al día en el sistema.")
