import streamlit as st
import pandas as pd
from datetime import datetime, date
import uuid
import time
from utils import conectar_google_sheets, ZONA_HORARIA

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
        records = ws.get_all_records()
        for row in records:
            if row.get("Parametro") == "FECHA_LANZAMIENTO":
                return datetime.strptime(row.get("Valor"), "%Y-%m-%d").date()
        return date.today()
    except:
        return date.today()

def cargar_datos(sheet):
    """Carga datos de forma robusta (ignorando encabezados dañados en recetas)."""
    try:
        # 1. INSUMOS
        ws_insumos = sheet.worksheet(HOJA_INSUMOS)
        df_insumos = pd.DataFrame(ws_insumos.get_all_records())
        
        # 2. RECETAS (Lectura por Posición para mayor seguridad)
        ws_recetas = sheet.worksheet(HOJA_RECETAS)
        matriz_raw = ws_recetas.get_all_values()
        
        if len(matriz_raw) > 1:
            df_raw = pd.DataFrame(matriz_raw[1:]) 
            # Mapeo: Col B(1)=Plato, Col D(3)=Ingrediente, Col E(4)=Cantidad
            if df_raw.shape[1] >= 5:
                df_recetas = df_raw.iloc[:, [1, 3, 4]].copy()
                df_recetas.columns = ["Nombre_Plato", "Ingrediente", "Cantidad_Gramos"]
            else:
                return None, None, None
        else:
            df_recetas = pd.DataFrame()

        return df_insumos, df_recetas, ws_insumos
    except Exception as e:
        st.error(f"Error cargando bases de datos: {e}")
        return None, None, None

def obtener_ventas_dia(sheet, fecha_str):
    try:
        ws = sheet.worksheet(HOJA_VENTAS)
        data = ws.get_all_records()
        if not data: return pd.DataFrame()
        
        df = pd.DataFrame(data)
        df["Fecha"] = df["Fecha"].astype(str)
        df_dia = df[df["Fecha"] == fecha_str]
        
        if df_dia.empty: return pd.DataFrame()

        # Normalización de nombre de plato
        col_nombre = "Nombre_Plato"
        if col_nombre not in df.columns:
            if len(df.columns) > 4: df = df.rename(columns={df.columns[4]: "Nombre_Plato"})
            else: col_nombre = "Producto"

        col_qty = "Cantidad_Vendida"
        if col_qty in df.columns:
            df[col_qty] = pd.to_numeric(df[col_qty], errors='coerce').fillna(0)
            resumen = df.groupby("Nombre_Plato")[col_qty].sum().reset_index()
            return resumen
        
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error leyendo ventas: {e}")
        return pd.DataFrame()

def ejecutar_explosion(sheet, df_ventas, df_recetas, df_insumos):
    movimientos_kardex = []
    insumos_afectados = {} 
    errores = []
    
    timestamp = datetime.now(ZONA_HORARIA)
    fecha_hoy = timestamp.strftime("%Y-%m-%d")
    hora_hoy = timestamp.strftime("%H:%M")

    for _, venta in df_ventas.iterrows():
        plato = str(venta["Nombre_Plato"]).strip()
        cantidad = float(venta["Cantidad_Vendida"])
        
        if cantidad <= 0: continue

        # Buscar Receta
        receta_plato = df_recetas[df_recetas["Nombre_Plato"].str.strip() == plato]
        
        if receta_plato.empty:
            # Ignorar items de sistema
            if plato not in ["TICKET", "Venta POS", "Propina", "Efectivo", "Nequi", "Venta Manual"]: 
                errores.append(f"Sin receta: {plato}")
            continue
            
        for _, linea in receta_plato.iterrows():
            insumo_nombre = str(linea["Ingrediente"]).strip()
            try:
                raw_cant = str(linea["Cantidad_Gramos"]).replace(",", ".")
                cant_receta = float(raw_cant)
            except: cant_receta = 0
            
            total_baja = cant_receta * cantidad
            
            # Buscar en Insumos
            datos_insumo = df_insumos[df_insumos["Nombre_Insumo"] == insumo_nombre]
            
            if datos_insumo.empty:
                continue
                
            # Calcular Saldos
            if insumo_nombre in insumos_afectados:
                stock_inicial = insumos_afectados[insumo_nombre]["stock_temp"]
            else:
                try: stock_inicial = float(str(datos_insumo.iloc[0]["Stock_Actual_Gr"]).replace(",", "."))
                except: stock_inicial = 0.0
            
            try: costo_unit = float(str(datos_insumo.iloc[0].get("Costo_Promedio_Ponderado", 0)).replace(",", "."))
            except: costo_unit = 0.0
            
            nuevo_stock = stock_inicial - total_baja
            
            insumos_afectados[insumo_nombre] = {
                "stock_temp": nuevo_stock,
                "fila_excel": datos_insumo.index[0] + 2 
            }
            
            mov = [
                generar_id_mov(), fecha_hoy, hora_hoy, "SALIDA (VENTA)",
                insumo_nombre, 0, total_baja, nuevo_stock, costo_unit
            ]
            movimientos_kardex.append(mov)

    if errores: 
        st.warning(f"⚠️ Algunos platos no tienen receta: {list(set(errores))[:5]}...")

    if not movimientos_kardex: return False

    try:
        ws_insumos = sheet.worksheet(HOJA_INSUMOS)
        ws_kardex = sheet.worksheet(HOJA_KARDEX)
        
        progreso = st.progress(0)
        total = len(insumos_afectados)
        i = 0
        
        for insumo, datos in insumos_afectados.items():
            # Actualizar Stock en Columna 7 (G)
            ws_insumos.update_cell(datos["fila_excel"], 7, datos["stock_temp"])
            i += 1
            progreso.progress(i / total)
            
        ws_kardex.append_rows(movimientos_kardex)
        return True
        
    except Exception as e:
        st.error(f"Error escribiendo: {e}")
        return False

# --- INTERFAZ PRINCIPAL ---
def show(sheet):
    st.title("📦 Inventario & Valorización")
    
    # 1. VALORIZACIÓN DE INVENTARIO (NUEVO BLOQUE)
    df_insumos, _, _ = cargar_datos(sheet)
    
    if df_insumos is not None and not df_insumos.empty:
        # Limpieza de datos para cálculo matemático
        df_insumos["Stock_Actual_Gr"] = pd.to_numeric(df_insumos["Stock_Actual_Gr"], errors='coerce').fillna(0)
        df_insumos["Costo_Promedio_Ponderado"] = pd.to_numeric(df_insumos["Costo_Promedio_Ponderado"], errors='coerce').fillna(0)
        df_insumos["Costo_Ultima_Compra"] = pd.to_numeric(df_insumos["Costo_Ultima_Compra"], errors='coerce').fillna(0)
        
        # Lógica de Costo: Usamos Promedio, si es 0, usamos Última Compra
        df_insumos["Costo_Calc"] = df_insumos.apply(
            lambda x: x["Costo_Promedio_Ponderado"] if x["Costo_Promedio_Ponderado"] > 0 else x["Costo_Ultima_Compra"], axis=1
        )
        
        # Cálculo del Valor Total (Stock * Costo)
        valor_total_inventario = (df_insumos["Stock_Actual_Gr"] * df_insumos["Costo_Calc"]).sum()
        total_items_stock = len(df_insumos[df_insumos["Stock_Actual_Gr"] > 0])
        
        # Tarjetas KPI
        kpi1, kpi2 = st.columns(2)
        kpi1.metric("💰 Valor del Inventario (Hoy)", formato_moneda(valor_total_inventario), help="Dinero total invertido en insumos actualmente en bodega.")
        kpi2.metric("📦 Referencias con Stock", f"{total_items_stock} ítems")
        
        st.markdown("---")

    # 2. EXPLOSIÓN DE MATERIALES (CON CANDADO)
    fecha_lanzamiento = obtener_fecha_lanzamiento(sheet)
    hoy_co = datetime.now(ZONA_HORARIA).date()
    
    col1, col2 = st.columns([1, 2])
    fecha_proc = col1.date_input("Fecha de Ventas a Procesar", value=hoy_co)
    fecha_str = fecha_proc.strftime("%Y-%m-%d")
    
    with col2:
        st.info("Este proceso descuenta ingredientes basándose en las ventas del día seleccionado.")

    # Lógica del Candado
    if fecha_proc < fecha_lanzamiento:
        st.warning(f"🔒 **MODO HISTÓRICO:** No se puede afectar inventario antes del {fecha_lanzamiento}.")
    else:
        if st.button("🚀 EJECUTAR DESCUENTO DE INVENTARIO", type="primary"):
            with st.spinner(f"Analizando ventas del {fecha_str}..."):
                df_insumos, df_recetas, _ = cargar_datos(sheet)
                
                if df_recetas is not None:
                    df_ventas = obtener_ventas_dia(sheet, fecha_str)
                    
                    if not df_ventas.empty:
                        if ejecutar_explosion(sheet, df_ventas, df_recetas, df_insumos):
                            st.balloons()
                            st.success(f"✅ ¡Inventario actualizado correctamente!")
                            time.sleep(2)
                            st.rerun()
                    else:
                        st.warning(f"No hay ventas registradas el {fecha_str}.")

    # 3. KARDEX RECIENTE
    st.markdown("---")
    with st.expander("📊 Ver Kardex (Últimos Movimientos)"):
        try:
            ws = sheet.worksheet(HOJA_KARDEX)
            df_k = pd.DataFrame(ws.get_all_records()).tail(10)
            # Fix PyArrow
            for c in df_k.columns: df_k[c] = df_k[c].astype(str)
            st.table(df_k)
        except: pass