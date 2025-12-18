import streamlit as st
import pandas as pd
from datetime import datetime, date
import subprocess
from utils import conectar_google_sheets, leer_datos_seguro

HOJA_CONFIG = "DB_CONFIG"

def guardar_parametro(sheet, parametro, valor):
    try:
        ws = sheet.worksheet(HOJA_CONFIG)
        cell = ws.find(parametro)
        if cell: ws.update_cell(cell.row, 2, str(valor))
        else: ws.append_row([parametro, str(valor)])
        return True
    except: return False

def obtener_config(sheet):
    try:
        ws = sheet.worksheet(HOJA_CONFIG)
        data = ws.get_all_records()
        return {row["Parametro"]: row["Valor"] for row in data}
    except: return {}

def show(sheet):
    st.title("⚙️ Configuración del Sistema")
    st.caption("Ajustes generales y conexiones.")
    st.markdown("---")
    
    if not sheet: return
    config = obtener_config(sheet)

    tab1, tab2, tab3 = st.tabs(["🏢 GENERAL", "🚀 OPERACIÓN", "☁️ SINCRONIZACIÓN"])

    # --- TAB 1: IDENTIDAD ---
    with tab1:
        st.subheader("Identidad del Negocio")
        
        col1, col2 = st.columns(2)
        actual_nombre = config.get("EMPRESA_NOMBRE", "TRIDENTI V7")
        actual_tema = config.get("MODO_OSCURO", "Auto")
        
        nuevo_nombre = col1.text_input("Nombre de la Empresa", value=actual_nombre)
        nuevo_tema = col2.selectbox("Tema Visual", ["Auto", "Dark (Oscuro)", "Light (Claro)"], index=0 if "Auto" in actual_tema else (1 if "Dark" in actual_tema else 2))
        
        if st.button("💾 Guardar Identidad", type="primary"):
            guardar_parametro(sheet, "EMPRESA_NOMBRE", nuevo_nombre)
            guardar_parametro(sheet, "MODO_OSCURO", nuevo_tema)
            st.success("Configuración actualizada. Recarga la página para ver cambios.")
            st.rerun()

    # --- TAB 2: OPERACIÓN (FECHAS) ---
    with tab2:
        st.subheader("Estrategia de Lanzamiento")
        st.info("Define cuándo empieza tu inventario real.")
        
        fecha_guardada = config.get("FECHA_LANZAMIENTO", str(date.today()))
        try: fecha_def = datetime.strptime(fecha_guardada, "%Y-%m-%d").date()
        except: fecha_def = date.today()
        
        nueva_fecha = st.date_input("Fecha de 'Go Live' (Inventario)", value=fecha_def)
        
        if st.button("💾 Guardar Fecha Operativa"):
            if guardar_parametro(sheet, "FECHA_LANZAMIENTO", nueva_fecha):
                st.success(f"Inventario bloqueado para fechas anteriores al {nueva_fecha}.")

        # Espacio para el link de Looker si decides volver a usarlo
        st.markdown("---")
        st.write("#### 📊 Enlaces Externos")
        link_looker = config.get("LINK_LOOKER", "")
        nuevo_link = st.text_input("Link Reporte Looker Studio (Opcional)", value=link_looker)
        if st.button("Guardar Link"):
            guardar_parametro(sheet, "LINK_LOOKER", nuevo_link)
            st.success("Guardado.")

    # --- TAB 3: SINCRONIZACIÓN (LA SOLUCIÓN) ---
    with tab3:
        st.subheader("Conexión con Loyverse")
        
        st.info("""
        **¿Cuándo usar este botón?**
        1. Cuando crees productos nuevos en Loyverse.
        2. Cuando cambies precios o nombres.
        3. Cuando elimines productos.
        
        Esto actualiza la base de datos interna para que las Recetas y Ventas funcionen bien.
        """)
        
        col_btn, col_res = st.columns([1, 2])
        
        with col_btn:
            if st.button("🔄 SINCRONIZAR MENÚ AHORA", type="primary"):
                with st.status("Conectando con la nube...", expanded=True) as status:
                    st.write("Descargando catálogo de productos...")
                    try:
                        # Ejecutamos el script independiente
                        subprocess.run(["python", "sincronizar_loyverse.py"], check=True)
                        status.update(label="¡Sincronización Exitosa!", state="complete", expanded=False)
                        st.balloons()
                        st.success("✅ La base de datos de productos está al día.")
                    except Exception as e:
                        status.update(label="Error", state="error")
                        st.error(f"Fallo al ejecutar el script: {e}")