import streamlit as st
import pandas as pd
from datetime import datetime
import uuid
import time
from utils import conectar_google_sheets, ZONA_HORARIA

HOJA_INSUMOS = "DB_INSUMOS"
HOJA_KARDEX = "KARDEX_MOVIMIENTOS"

def cargar_insumos(sheet):
    """Lectura segura de insumos."""
    try:
        ws = sheet.worksheet(HOJA_INSUMOS)
        data = ws.get_all_values()
        
        if len(data) < 2:
            return pd.DataFrame(columns=["Nombre_Insumo", "Categoria", "Unidad_Compra", "Stock_Actual_Gr", "Costo_Promedio_Ponderado", "ID_Insumo"]), ws
            
        headers = data[0]
        rows = data[1:]
        df = pd.DataFrame(rows, columns=headers)
        
        # Limpieza de números para evitar errores de texto
        # (Si está vacío pone 0)
        col_stock = "Stock_Actual_Gr"
        if col_stock in df.columns:
            df[col_stock] = df[col_stock].apply(lambda x: float(str(x).replace(",", ".") or 0) if str(x).strip() else 0.0)
            
        return df, ws
    except: return None, None

def guardar_ajuste(sheet, movimientos, actualizaciones_stock):
    try:
        ws_kardex = sheet.worksheet(HOJA_KARDEX)
        ws_insumos = sheet.worksheet(HOJA_INSUMOS)
        
        ws_kardex.append_rows(movimientos)
        
        progreso = st.progress(0)
        total = len(actualizaciones_stock)
        i = 0
        for fila, nuevo_valor in actualizaciones_stock:
            ws_insumos.update_cell(fila, 7, nuevo_valor) # Columna G
            i += 1
            progreso.progress(i / total)
        return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False

def show(sheet):
    st.title("🕵️ Auditoría Ciega de Inventario")
    
    with st.expander("📘 ¿CÓMO FUNCIONA ESTO?", expanded=True):
        st.markdown("Cuenta lo que ves en físico y escríbelo. El sistema ajustará la diferencia.")
    
    st.markdown("---")
    
    if not sheet: return

    df, ws_insumos = cargar_insumos(sheet)
    
    if df is None or df.empty or "Nombre_Insumo" not in df.columns:
        st.warning("⚠️ Base de datos de insumos vacía. Agrega insumos primero.")
        return

    categorias = ["Seleccionar..."] + sorted(df["Categoria"].unique().tolist()) if "Categoria" in df.columns else []
    
    c1, c2 = st.columns(2)
    cat_sel = c1.selectbox("Filtro por Área:", categorias)
    responsable = c2.text_input("Nombre del Auditor")

    if cat_sel == "Seleccionar...":
        st.info("👈 Selecciona un área.")
        return

    # Filtrar
    df_conteo = df[df["Categoria"] == cat_sel].copy()
    df_conteo["Conteo_Fisico"] = 0.0

    # Crear visualización segura
    cols_necesarias = ["Nombre_Insumo", "Unidad_Compra", "Conteo_Fisico", "ID_Insumo", "Stock_Actual_Gr", "Costo_Promedio_Ponderado"]
    # Asegurar que existan todas
    for c in cols_necesarias:
        if c not in df_conteo.columns: df_conteo[c] = 0 # Rellenar si falta alguna
        
    df_display = df_conteo[cols_necesarias]
    
    st.write(f"📋 Listado de **{cat_sel}**:")
    
    df_editado = st.data_editor(
        df_display,
        column_config={
            "Nombre_Insumo": st.column_config.TextColumn("Insumo", disabled=True),
            "Unidad_Compra": st.column_config.TextColumn("Unidad", disabled=True),
            "Conteo_Fisico": st.column_config.NumberColumn("📝 CANTIDAD CONTADA", min_value=0.0, step=0.5, required=True),
        },
        disabled=["Nombre_Insumo", "Unidad_Compra", "ID_Insumo", "Stock_Actual_Gr", "Costo_Promedio_Ponderado"],
        hide_index=True,
        use_container_width=True
    )

    st.markdown("---")
    
    if st.button("⚖️ TERMINAR Y GUARDAR", type="primary"):
        if not responsable:
            st.warning("⚠️ Falta tu nombre.")
            return

        ajustes = []
        updates = []
        cambios = False
        
        fecha = datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d")
        hora = datetime.now(ZONA_HORARIA).strftime("%H:%M")

        for i, row in df_editado.iterrows():
            fisico = float(row["Conteo_Fisico"])
            teorico = float(row["Stock_Actual_Gr"])
            
            if fisico != teorico:
                cambios = True
                diferencia = fisico - teorico
                costo = float(str(row["Costo_Promedio_Ponderado"]).replace(",", ".") or 0)
                
                try:
                    cell = ws_insumos.find(str(row["ID_Insumo"]))
                    fila_real = cell.row
                    updates.append((fila_real, fisico))
                    
                    tipo = "AJUSTE SOBRANTE" if diferencia > 0 else "AJUSTE PÉRDIDA"
                    # ID, Fecha, Hora, Tipo, Insumo, Ent, Sal, Saldo, Costo, Detalle
                    mov = [
                        f"AUD-{str(uuid.uuid4())[:4]}",
                        fecha, hora, tipo,
                        row["Nombre_Insumo"],
                        diferencia if diferencia > 0 else 0,
                        abs(diferencia) if diferencia < 0 else 0,
                        fisico, costo,
                        f"Auditor: {responsable}"
                    ]
                    ajustes.append(mov)
                except: pass

        if cambios:
            with st.spinner("Guardando..."):
                if guardar_ajuste(sheet, ajustes, updates):
                    st.success("✅ Auditoría Guardada.")
                    time.sleep(2)
                    st.rerun()
        else:
            st.info("No hay cambios.")