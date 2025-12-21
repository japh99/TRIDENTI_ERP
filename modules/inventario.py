import streamlit as st
import pandas as pd
from datetime import datetime, date
import uuid
import time
from utils import conectar_google_sheets, ZONA_HORARIA, leer_datos_seguro

# --- CONFIGURACIÓN DE HOJAS ---
HOJA_INSUMOS = "DB_INSUMOS"
HOJA_RECETAS = "DB_RECETAS"
HOJA_VENTAS = "LOG_VENTAS_LOYVERSE"
HOJA_KARDEX = "KARDEX_MOVIMIENTOS"
HOJA_CONFIG = "DB_CONFIG"

# --- UTILIDADES ---
def generar_id_mov():
    return f"MOV-{str(uuid.uuid4())[:4].upper()}"

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

def obtener_fecha_lanzamiento(sheet):
    """Consulta la fecha de 'Go Live' para el candado de seguridad."""
    try:
        ws = sheet.worksheet(HOJA_CONFIG)
        # Usamos leer_datos_seguro para evitar bloqueos de caché
        df_conf = leer_datos_seguro(ws)
        if not df_conf.empty and "Parametro" in df_conf.columns:
            res = df_conf[df_conf["Parametro"] == "FECHA_LANZAMIENTO"]
            if not res.empty:
                return datetime.strptime(res.iloc[0]["Valor"], "%Y-%m-%d").date()
        return date(2025, 1, 1) # Fecha por defecto antigua si no existe
    except:
        return date.today()

def cargar_datos(sheet):
    """Carga datos de forma robusta manejando hojas vacías."""
    try:
        # 1. INSUMOS
        ws_insumos = sheet.worksheet(HOJA_INSUMOS)
        # USAMOS leer_datos_seguro para que si la hoja está vacía devuelva un DF con columnas
        df_insumos = leer_datos_seguro(ws_insumos)
        
        # 2. RECETAS
        ws_recetas = sheet.worksheet(HOJA_RECETAS)
        matriz_raw = ws_recetas.get_all_values()
        
        if len(matriz_raw) > 1:
            df_raw = pd.DataFrame(matriz_raw[1:]) 
            if df_raw.shape[1] >= 5:
                df_recetas = df_raw.iloc[:, [1, 3, 4]].copy()
                df_recetas.columns = ["Nombre_Plato", "Ingrediente", "Cantidad_Gramos"]
            else:
                df_recetas = pd.DataFrame(columns=["Nombre_Plato", "Ingrediente", "Cantidad_Gramos"])
        else:
            df_recetas = pd.DataFrame(columns=["Nombre_Plato", "Ingrediente", "Cantidad_Gramos"])
            
        return df_insumos, df_recetas, ws_insumos
    except Exception as e:
        st.error(f"Error cargando bases de datos: {e}")
        return pd.DataFrame(), pd.DataFrame(), None

# ... (obtener_ventas_dia y ejecutar_explosion se mantienen igual) ...

def show(sheet):
    st.title("📦 Inventario & Valorización")
    
    # BOTÓN PARA FORZAR ACTUALIZACIÓN (Esto limpia el caché que te da problemas)
    if st.button("🔄 Sincronizar con Excel (Limpiar Caché)"):
        st.cache_data.clear()
        st.rerun()

    # 1. VALORIZACIÓN DE INVENTARIO
    df_insumos, _, _ = cargar_datos(sheet)
    
    valor_total_inventario = 0.0
    total_items_stock = 0

    if not df_insumos.empty and "Stock_Actual_Gr" in df_insumos.columns:
        # Limpieza estricta de datos
        df_insumos["Stock_Actual_Gr"] = pd.to_numeric(df_insumos["Stock_Actual_Gr"], errors='coerce').fillna(0)
        df_insumos["Costo_Promedio_Ponderado"] = pd.to_numeric(df_insumos.get("Costo_Promedio_Ponderado", 0), errors='coerce').fillna(0)
        df_insumos["Costo_Ultima_Compra"] = pd.to_numeric(df_insumos.get("Costo_Ultima_Compra", 0), errors='coerce').fillna(0)
        
        # Lógica de Costo
        df_insumos["Costo_Calc"] = df_insumos.apply(
            lambda x: x["Costo_Promedio_Ponderado"] if x["Costo_Promedio_Ponderado"] > 0 else x["Costo_Ultima_Compra"], axis=1
        )
        
        valor_total_inventario = (df_insumos["Stock_Actual_Gr"] * df_insumos["Costo_Calc"]).sum()
        total_items_stock = len(df_insumos[df_insumos["Stock_Actual_Gr"] > 0])

    # Tarjetas KPI (Ahora siempre mostrarán 0 si no hay datos)
    kpi1, kpi2 = st.columns(2)
    kpi1.metric("Valor del Inventario (Hoy)", formato_moneda(valor_total_inventario))
    kpi2.metric("Referencias con Stock", f"{total_items_stock} ítems")
    
    st.markdown("---")

    # 2. EXPLOSIÓN DE MATERIALES
    fecha_lanzamiento = obtener_fecha_lanzamiento(sheet)
    hoy_co = datetime.now(ZONA_HORARIA).date()
    
    col1, col2 = st.columns([1, 2])
    fecha_proc = col1.date_input("Fecha de Ventas a Procesar", value=hoy_co)
    fecha_str = fecha_proc.strftime("%Y-%m-%d")
    
    with col2:
        st.info("Este proceso descuenta ingredientes basándose en las ventas del día.")

    # Lógica del Candado
    if fecha_proc < fecha_lanzamiento:
        st.warning(f"🔒 **MODO HISTÓRICO:** No se puede afectar inventario antes del {fecha_lanzamiento}. (Cambia la FECHA_LANZAMIENTO en DB_CONFIG para liberar).")
    else:
        if st.button("🚀 EJECUTAR DESCUENTO DE INVENTARIO", type="primary"):
            # Lógica de ejecución...
            pass

    # 3. KARDEX RECIENTE
    st.markdown("---")
    with st.expander("📊 Ver Kardex (Últimos Movimientos)"):
        try:
            ws_k = sheet.worksheet(HOJA_KARDEX)
            df_k = leer_datos_seguro(ws_k)
            if not df_k.empty:
                st.table(df_k.tail(15))
            else:
                st.write("No hay movimientos registrados.")
        except: st.write("Kardex no disponible.")
