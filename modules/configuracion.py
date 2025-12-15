import streamlit as st
import pandas as pd
from utils import leer_datos_seguro

def show(sheet):
    st.header("⚙️ Configuración del Sistema")
    
    try:
        hoja_config = sheet.worksheet("DB_CONFIG")
        df_config = leer_datos_seguro(hoja_config)
    except:
        st.error("⚠️ No se encontró la pestaña 'DB_CONFIG' en el Excel.")
        st.info("Por favor crea la pestaña con columnas: Parametro, Valor, Descripcion")
        return

    # Convertir a Diccionario para fácil acceso
    if not df_config.empty:
        config_dict = dict(zip(df_config['Parametro'], df_config['Valor']))
    else:
        config_dict = {}

    st.markdown("---")

    with st.form("form_config"):
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("🏢 Identidad")
            val_nombre = config_dict.get("EMPRESA_NOMBRE", "Mi Restaurante")
            nuevo_nombre = st.text_input("Nombre del Negocio", value=val_nombre)
            
            st.subheader("🎨 Apariencia")
            val_tema = config_dict.get("MODO_OSCURO", "Auto")
            opciones_tema = ["Auto", "Dark (Oscuro)", "Light (Claro)"]
            
            # Buscar índice actual
            idx_tema = 0
            if "Dark" in val_tema: idx_tema = 1
            elif "Light" in val_tema: idx_tema = 2
            
            nuevo_tema = st.selectbox("Tema Visual", opciones_tema, index=idx_tema, help="Requiere recargar la página.")

        with c2:
            st.subheader("💰 Formato Financiero")
            val_moneda = config_dict.get("MONEDA_SIMBOLO", "$")
            nuevo_moneda = st.text_input("Símbolo Moneda", value=val_moneda)
            
            val_decimales = int(config_dict.get("DECIMALES", 0))
            nuevo_decimales = st.selectbox("Decimales en Precios", [0, 2], index=0 if val_decimales==0 else 1)
            
            val_iva = config_dict.get("IVA_PORCENTAJE", "0")
            nuevo_iva = st.number_input("% Impuesto (IVA/ICO)", value=float(val_iva))

        st.markdown("---")
        st.subheader("🔔 Alertas")
        val_stock = float(config_dict.get("STOCK_ALERTA", 5))
        nuevo_stock = st.slider("Alerta de Stock Bajo (Unidades/Kg)", 1.0, 100.0, val_stock)

        if st.form_submit_button("💾 GUARDAR CONFIGURACIÓN", type="primary"):
            try:
                # Actualizar cada celda en el Excel
                # Buscamos la fila del parámetro y actualizamos la columna B (2)
                
                # Mapa de actualizaciones
                cambios = {
                    "EMPRESA_NOMBRE": nuevo_nombre,
                    "MONEDA_SIMBOLO": nuevo_moneda,
                    "DECIMALES": nuevo_decimales,
                    "MODO_OSCURO": nuevo_tema,
                    "IVA_PORCENTAJE": nuevo_iva,
                    "STOCK_ALERTA": nuevo_stock
                }
                
                # Actualización masiva eficiente
                # Borramos hoja y reescribimos para evitar errores de búsqueda
                nuevos_datos = [["Parametro", "Valor", "Descripcion"]] # Encabezados
                
                nuevos_datos.append(["EMPRESA_NOMBRE", nuevo_nombre, "Nombre del negocio"])
                nuevos_datos.append(["MONEDA_SIMBOLO", nuevo_moneda, "Símbolo de moneda"])
                nuevos_datos.append(["DECIMALES", nuevo_decimales, "Cantidad de decimales"])
                nuevos_datos.append(["MODO_OSCURO", nuevo_tema, "Tema visual"])
                nuevos_datos.append(["IVA_PORCENTAJE", nuevo_iva, "Impuesto por defecto"])
                nuevos_datos.append(["STOCK_ALERTA", nuevo_stock, "Alerta stock bajo"])
                
                hoja_config.clear()
                hoja_config.update(range_name="A1", values=nuevos_datos)
                
                st.success("✅ Configuración guardada correctamente.")
                st.info("🔄 Recarga la página para ver los cambios de diseño.")
                
            except Exception as e:
                st.error(f"Error guardando: {e}")