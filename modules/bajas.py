import streamlit as st
import pandas as pd
from datetime import datetime
import uuid
import time
from utils import conectar_google_sheets, subir_foto_drive, generar_id, ZONA_HORARIA

# --- CONFIGURACIÓN ---
HOJA_INSUMOS = "DB_INSUMOS"
HOJA_KARDEX = "KARDEX_MOVIMIENTOS"

def cargar_insumos(sheet):
    """Carga insumos de forma segura incluso si la hoja está casi vacía."""
    try:
        ws = sheet.worksheet(HOJA_INSUMOS)
        # Usamos get_all_values para leer todo (incluyendo headers)
        data = ws.get_all_values()
        
        if len(data) < 2:
            # Si hay menos de 2 filas (solo headers o nada), retornamos estructura vacía segura
            return pd.DataFrame(columns=["Nombre_Insumo", "Unidad_Compra", "Stock_Actual_Gr", "Costo_Promedio_Ponderado"]), ws
            
        # Si hay datos, procesamos normal
        headers = data[0]
        rows = data[1:]
        df = pd.DataFrame(rows, columns=headers)
        return df, ws
    except Exception as e:
        return None, None

def registrar_baja(sheet, datos_kardex, fila_insumo, nuevo_stock):
    try:
        ws_kardex = sheet.worksheet(HOJA_KARDEX)
        ws_insumos = sheet.worksheet(HOJA_INSUMOS)
        ws_insumos.update_cell(fila_insumo, 7, nuevo_stock) # Col G
        ws_kardex.append_row(datos_kardex)
        return True
    except Exception as e:
        st.error(f"Error registrando baja: {e}")
        return False

def show(sheet):
    st.header("🗑️ Reportar Daño / Merma")
    
    with st.expander("📘 INSTRUCCIONES (LEER ANTES)", expanded=False):
        st.markdown("""
        1. **Busca el producto** que se dañó.
        2. **Ingresa la cantidad** exacta.
        3. **Sube la foto** obligatoria.
        4. **Escribe el motivo** real.
        """)
    st.markdown("---")
    
    if not sheet: return

    df, ws_insumos = cargar_insumos(sheet)
    
    # Validación si la base de datos está vacía
    if df is None or df.empty or "Nombre_Insumo" not in df.columns:
        st.warning("⚠️ No hay insumos registrados en la base de datos. Ve al módulo 'Insumos' y crea el primero.")
        return

    col1, col2 = st.columns(2)
    
    with col1:
        lista_insumos = df["Nombre_Insumo"].tolist()
        if not lista_insumos:
            st.info("Lista de insumos vacía.")
            return
            
        insumo_sel = st.selectbox("¿Qué se dañó?", lista_insumos)
        
        # Obtener datos seguros
        info_insumo = df[df["Nombre_Insumo"] == insumo_sel].iloc[0]
        
        try:
            stock_val = str(info_insumo.get("Stock_Actual_Gr", "0")).replace(",", ".")
            stock_actual = float(stock_val) if stock_val else 0.0
        except: stock_actual = 0.0
        
        unidad = info_insumo.get("Unidad_Compra", "Unid")
        
        st.info(f"Stock en Sistema: {stock_actual} ({unidad})")
        
        cantidad = st.number_input("Cantidad Dañada", min_value=0.1, step=0.5)
        motivo = st.selectbox("Motivo", ["Quemado / Error Cocina", "Vencimiento", "Caída / Accidente", "Calidad Proveedor", "Consumo Personal"])
        
    with col2:
        responsable = st.text_input("¿Quién reporta?", placeholder="Tu nombre")
        nota = st.text_area("Detalle", placeholder="Explica qué pasó...")
        foto = st.file_uploader("📸 FOTO OBLIGATORIA", type=["jpg", "png", "jpeg"])

    if st.button("🚨 REGISTRAR PÉRDIDA", type="primary", use_container_width=True):
        if cantidad > 0 and responsable and foto:
            with st.status("Subiendo evidencia...", expanded=True):
                url_foto = subir_foto_drive(foto, subcarpeta="EVIDENCIA_MERMAS")
                
                if "Error" not in url_foto:
                    nuevo_stock = stock_actual - cantidad
                    
                    try:
                        costo_val = str(info_insumo.get("Costo_Promedio_Ponderado", "0")).replace(",", ".")
                        costo = float(costo_val) if costo_val else 0.0
                    except: costo = 0.0
                    
                    # Buscar fila real (+2 por header y base 0)
                    fila_excel = df[df["Nombre_Insumo"] == insumo_sel].index[0] + 2
                    
                    fecha = datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d")
                    hora = datetime.now(ZONA_HORARIA).strftime("%H:%M")
                    
                    mov = [
                        generar_id(), fecha, hora, 
                        f"SALIDA ({motivo.upper()})", 
                        insumo_sel, 0, cantidad, 
                        nuevo_stock, costo, 
                        f"{nota} | Resp: {responsable} | Foto: {url_foto}"
                    ]
                    
                    if registrar_baja(sheet, mov, fila_excel, nuevo_stock):
                        st.success("✅ Baja registrada correctamente.")
                        time.sleep(2)
                        st.rerun()
                else:
                    st.error("Error subiendo foto.")
        else:
            st.warning("⚠️ Faltan datos o foto.")

    st.markdown("---")
    st.subheader("📜 Historial de Mermas Recientes")
    try:
        ws_kardex = sheet.worksheet(HOJA_KARDEX)
        data = ws_kardex.get_all_records()
        if data:
            df_k = pd.DataFrame(data)
            # Verificar si existe la columna antes de filtrar
            if "Tipo_Movimiento" in df_k.columns:
                df_mermas = df_k[df_k["Tipo_Movimiento"].str.contains("SALIDA") & ~df_k["Tipo_Movimiento"].str.contains("VENTA")]
                if not df_mermas.empty:
                    st.dataframe(df_mermas.tail(10), use_container_width=True, hide_index=True)
                else:
                    st.info("No hay mermas registradas.")
            else:
                st.info("Kardex sin estructura de movimientos.")
    except: pass