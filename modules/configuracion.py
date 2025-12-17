import streamlit as st
import pandas as pd
from datetime import datetime, date
from utils import conectar_google_sheets

HOJA_CONFIG = "DB_CONFIG"

def guardar_parametro(sheet, parametro, valor):
    """Busca si el parámetro existe y lo actualiza, o lo crea."""
    try:
        ws = sheet.worksheet(HOJA_CONFIG)
        # Buscar en la columna A (Parametro)
        celda = ws.find(parametro)
        
        if celda:
            # Si existe, actualizamos la celda de al lado (Columna B)
            ws.update_cell(celda.row, 2, str(valor))
        else:
            # Si no existe, lo agregamos al final
            ws.append_row([parametro, str(valor)])
        return True
    except Exception as e:
        st.error(f"Error guardando configuración: {e}")
        return False

def obtener_config(sheet):
    """Lee toda la configuración y la devuelve como diccionario."""
    try:
        ws = sheet.worksheet(HOJA_CONFIG)
        data = ws.get_all_records()
        # Convertir lista de dicts a un solo dict {Parametro: Valor}
        return {row["Parametro"]: row["Valor"] for row in data}
    except:
        return {}

def show(sheet):
    st.title("⚙️ Configuración del Sistema")
    st.markdown("---")
    
    if not sheet: return

    # Cargar configuración actual
    config_actual = obtener_config(sheet)
    
    st.subheader("📅 Estrategia de Lanzamiento")
    st.info("Define la fecha exacta en la que inicias el control real de inventario (Día Cero).")
    
    # Obtener fecha guardada o usar hoy por defecto
    fecha_guardada_str = config_actual.get("FECHA_LANZAMIENTO", str(date.today()))
    try:
        fecha_default = datetime.strptime(fecha_guardada_str, "%Y-%m-%d").date()
    except:
        fecha_default = date.today()

    col1, col2 = st.columns([1, 2])
    
    with col1:
        nueva_fecha = st.date_input("Fecha de 'Go Live' (Inicio Operativo)", value=fecha_default)
        
        if st.button("💾 GUARDAR FECHA DE LANZAMIENTO", type="primary"):
            if guardar_parametro(sheet, "FECHA_LANZAMIENTO", nueva_fecha):
                st.success(f"✅ Sistema configurado. El inventario solo se descontará a partir del {nueva_fecha}.")
                st.balloons()
            else:
                st.error("No se pudo guardar.")

    with col2:
        st.write("### ¿Qué hace esto?")
        st.caption(f"""
        1. **Modo Histórico:** Cualquier venta anterior al **{nueva_fecha}** será tratada solo como estadística (sin descontar inventario).
        2. **Modo Operativo:** A partir del **{nueva_fecha}**, el botón de 'Explosión de Materiales' se activará para descontar stock real.
        """)

    st.markdown("---")
    with st.expander("🔧 Ver parámetros técnicos"):
        st.json(config_actual)