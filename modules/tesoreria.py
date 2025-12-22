import streamlit as st
import pandas as pd
from datetime import datetime
import time
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero, formato_moneda

# --- CONFIGURACIÓN DE HOJAS ---
HOJA_VENTAS = "LOG_VENTAS_LOYVERSE"
HOJA_CIERRES = "LOG_CIERRES_CAJA"

def show(sheet):
    st.title("🔐 Tesorería: Consulta por Cierres")
    st.caption("Visualiza los tickets desglosados de cada cierre realizado.")
    
    if not sheet: return

    # --- 1. SELECCIÓN DE FECHA ---
    c_f1, c_f2 = st.columns([1, 2])
    fecha_consulta = c_f1.date_input("📅 Selecciona el día:", value=datetime.now(ZONA_HORARIA).date())
    fecha_str = fecha_consulta.strftime("%Y-%m-%d")

    # --- 2. CARGAR CIERRES REALIZADOS ESE DÍA ---
    try:
        ws_c = sheet.worksheet(HOJA_CIERRES)
        df_c = leer_datos_seguro(ws_c)
        df_c.columns = df_c.columns.str.strip() # Limpieza de nombres
    except:
        st.error("No se encontró la base de datos de cierres.")
        return

    if df_c.empty:
        st.warning("No hay ningún cierre registrado en el sistema aún.")
        return

    # Filtrar cierres del día
    cierres_dia = df_c[df_c["Fecha_Cierre"] == fecha_str].copy()

    if cierres_dia.empty:
        st.info(f"No se realizaron cierres el día {fecha_str}.")
        return

    # --- 3. SELECCIONAR UN CIERRE ESPECÍFICO ---
    st.markdown("### 🏁 Cierres encontrados")
    # Creamos una etiqueta bonita para el selector
    cierres_dia["Label"] = cierres_dia.apply(
        lambda x: f"Z-Report: {x.get('Numero_Cierre_Loyverse','S/N')} | Hora: {x.get('Hora_Cierre','--:--')} | Venta: {formato_moneda(x.get('Saldo_Teorico_E',0))}", 
        axis=1
    )
    
    seleccion_cierre = st.selectbox("Elige un cierre para ver sus detalles:", cierres_dia["Label"].tolist())
    
    # Obtener los datos del cierre seleccionado
    datos_cierre = cierres_dia[cierres_dia["Label"] == seleccion_cierre].iloc[0]
    t_ini = str(datos_cierre["Ticket_Ini"])
    t_fin = str(datos_cierre["Ticket_Fin"])

    # --- 4. MOSTRAR RESUMEN DEL CIERRE SELECCIONADO ---
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Efectivo Contado", formato_moneda(datos_cierre['Saldo_Real_Cor']))
    
    diff = float(limpiar_numero(datos_cierre['Diferencia']))
    color_diff = "normal" if diff == 0 else "inverse"
    col2.metric("Diferencia", formato_moneda(diff), delta=diff, delta_color=color_diff)
    
    col3.metric("Recibos", f"{t_ini} al {t_fin}")
    col4.metric("Z-Report", datos_cierre.get('Numero_Cierre_Loyverse', 'S/N'))

    # --- 5. BUSCAR Y CONSOLIDAR TICKETS DE ESTE CIERRE ---
    st.markdown("### 🎫 Desglose de Tickets en este Cierre")
    
    with st.spinner("Buscando tickets en el historial..."):
        try:
            ws_v = sheet.worksheet(HOJA_VENTAS)
            df_v_raw = leer_datos_seguro(ws_v)
            
            if not df_v_raw.empty:
                # Filtrar ventas que estén entre el Ticket_Ini y Ticket_Fin
                # Nota: Usamos el índice de la tabla para asegurar que tomamos el rango exacto
                recibos_list = df_v_raw["Numero_Recibo"].astype(str).tolist()
                
                if t_ini in recibos_list and t_fin in recibos_list:
                    idx_start = recibos_list.index(t_ini)
                    idx_end = recibos_list.index(t_fin)
                    
                    # El rango puede estar al revés dependiendo de la carga
                    start, end = (idx_start, idx_end) if idx_start < idx_end else (idx_end, idx_start)
                    df_v_turno = df_v_raw.iloc[start:end+1].copy()
                    
                    # Convertir a número para sumar
                    df_v_turno["Total_Dinero"] = pd.to_numeric(df_v_turno["Total_Dinero"], errors='coerce').fillna(0)

                    # CONSOLIDAR: Agrupar por recibo (para no ver productos repetidos)
                    df_resumen_tickets = df_v_turno.groupby("Numero_Recibo").agg({
                        "Hora": "first",
                        "Nombre_Plato": lambda x: f"{len(x)} items",
                        "Total_Dinero": "sum",
                        "Metodo_Pago_Loyverse": "first"
                    }).reset_index()

                    # Mostrar tabla profesional
                    st.dataframe(
                        df_resumen_tickets,
                        column_config={
                            "Numero_Recibo": "Ticket #",
                            "Total_Dinero": st.column_config.NumberColumn("Valor Total", format="$%d"),
                            "Nombre_Plato": "Contenido",
                            "Metodo_Pago_Loyverse": "Método Loyverse"
                        },
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    st.caption(f"Se muestran {len(df_resumen_tickets)} tickets consolidados pertenecientes a este cierre.")
                else:
                    st.warning("No se pudieron localizar los IDs de los tickets en la base de datos de ventas. Es posible que el historial de ventas haya sido modificado.")
        except Exception as e:
            st.error(f"Error cargando los tickets: {e}")

    # --- 6. BOTÓN DE ACTUALIZACIÓN ---
    st.markdown("---")
    if st.button("🔄 ACTUALIZAR DATOS"):
        st.cache_data.clear()
        st.rerun()
