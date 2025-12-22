import streamlit as st
import pandas as pd
from datetime import datetime
import time
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero

# --- CONFIGURACIÓN DE HOJAS ---
HOJA_VENTAS = "LOG_VENTAS_LOYVERSE"
HOJA_CIERRES = "LOG_CIERRES_CAJA"

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

def show(sheet):
    st.title("🔐 Auditoría de Cierres realizados")
    st.caption("Selecciona un cierre guardado para desglosar y auditar sus tickets.")
    
    if not sheet: return

    # --- 1. SELECCIÓN DE FECHA ---
    c_f1, c_f2 = st.columns([1, 2])
    fecha_consulta = c_f1.date_input("📅 Ver cierres del día:", value=datetime.now(ZONA_HORARIA).date())
    fecha_str = fecha_consulta.strftime("%Y-%m-%d")

    # --- 2. CARGAR CIERRES REALIZADOS ---
    try:
        ws_c = sheet.worksheet(HOJA_CIERRES)
        df_c = leer_datos_seguro(ws_c)
        if not df_c.empty:
            df_c.columns = df_c.columns.str.strip() # Limpiar encabezados
    except:
        st.error("No se encontró la base de datos de cierres.")
        return

    if df_c.empty:
        st.warning("No hay cierres registrados en el sistema.")
        return

    # Filtrar cierres por la fecha seleccionada
    # Buscamos en la columna 'Fecha' o 'Fecha_Cierre'
    col_f = "Fecha_Cierre" if "Fecha_Cierre" in df_c.columns else "Fecha"
    cierres_encontrados = df_c[df_c[col_f].astype(str) == fecha_str].copy()

    if cierres_encontrados.empty:
        st.info(f"No se encontraron registros de cierre para el día {fecha_str}.")
        return

    # --- 3. SELECCIONAR EL CIERRE A AUDITAR ---
    st.markdown("### 🏁 Cierres detectados en esta fecha")
    
    cierres_encontrados["Label"] = cierres_encontrados.apply(
        lambda x: f"Z-Report: {x.get('Numero_Cierre_Loyverse','S/N')} | Hora: {x.get('Hora_Cierre','--:--')} | Venta: {formato_moneda(x.get('Saldo_Teorico_E',0))}", 
        axis=1
    )
    
    seleccion = st.selectbox("Selecciona el cierre que deseas auditar:", cierres_encontrados["Label"].tolist())
    
    # Obtener datos del cierre seleccionado
    cierre_sel = cierres_encontrados[cierres_encontrados["Label"] == seleccion].iloc[0]
    t_ini = str(cierre_sel.get("Ticket_Ini", ""))
    t_fin = str(cierre_sel.get("Ticket_Fin", ""))

    if not t_ini or not t_fin:
        st.error("Este cierre no tiene guardado el rango de tickets (Ticket_Ini / Ticket_Fin).")
        return

    # --- 4. CARGAR Y CONSOLIDAR TICKETS DEL RANGO ---
    st.markdown("---")
    st.subheader(f"🎫 Auditoría de Tickets (#{t_ini} al #{t_fin})")
    
    with st.spinner("Buscando tickets en el historial de ventas..."):
        try:
            ws_v = sheet.worksheet(HOJA_VENTAS)
            df_v_raw = leer_datos_seguro(ws_v)
            
            if not df_v_raw.empty:
                # Estandarizar Numero_Recibo
                df_v_raw["Numero_Recibo"] = df_v_raw["Numero_Recibo"].astype(str).str.strip()
                lista_recibos = df_v_raw["Numero_Recibo"].tolist()
                
                if t_ini in lista_recibos and t_fin in lista_recibos:
                    idx_i = lista_recibos.index(t_ini)
                    idx_f = lista_recibos.index(t_fin)
                    
                    # Cortar el rango exacto
                    start, end = (idx_i, idx_f) if idx_i < idx_f else (idx_f, idx_i)
                    df_turno = df_v_raw.iloc[start:end+1].copy()
                    
                    # Convertir montos a número
                    df_turno["Total_Dinero"] = pd.to_numeric(df_turno["Total_Dinero"], errors='coerce').fillna(0)

                    # CONSOLIDAR: Unir productos de un mismo ticket en una sola fila
                    df_audit = df_turno.groupby("Numero_Recibo").agg({
                        "Hora": "first",
                        "Total_Dinero": "sum",
                        "Metodo_Pago_Loyverse": "first"
                    }).reset_index()

                    # Inicializar columnas para que el usuario edite
                    df_audit["Efectivo_Real"] = df_audit.apply(lambda x: x["Total_Dinero"] if x["Metodo_Pago_Loyverse"] == "Efectivo" else 0.0, axis=1)
                    df_audit["Nequi_Real"] = df_audit.apply(lambda x: x["Total_Dinero"] if "Nequi" in str(x["Metodo_Pago_Loyverse"]) else 0.0, axis=1)
                    df_audit["Tarjeta_Real"] = df_audit.apply(lambda x: x["Total_Dinero"] if "Tarjeta" in str(x["Metodo_Pago_Loyverse"]) else 0.0, axis=1)
                    df_audit["Validación"] = df_audit["Efectivo_Real"] + df_audit["Nequi_Real"] + df_audit["Tarjeta_Real"]

                    # --- TABLA DE EDICIÓN ---
                    df_ed = st.data_editor(
                        df_audit[["Numero_Recibo", "Hora", "Total_Dinero", "Efectivo_Real", "Nequi_Real", "Tarjeta_Real", "Validación"]],
                        column_config={
                            "Numero_Recibo": "Ticket #",
                            "Total_Dinero": st.column_config.NumberColumn("Valor Total", format="$%d", disabled=True),
                            "Efectivo_Real": st.column_config.NumberColumn("Efectivo $", format="$%d"),
                            "Nequi_Real": st.column_config.NumberColumn("Nequi $", format="$%d"),
                            "Tarjeta_Real": st.column_config.NumberColumn("Tarjeta $", format="$%d"),
                            "Validación": st.column_config.NumberColumn("Suma", format="$%d", disabled=True),
                        },
                        hide_index=True, use_container_width=True, key="editor_auditoria_cierre"
                    )

                    # --- RESULTADOS DE LA AUDITORÍA ---
                    st.markdown("### 📊 Resultado de la Auditoría")
                    v_total = df_ed["Total_Dinero"].sum()
                    v_efec = df_ed["Efectivo_Real"].sum()
                    v_nequi = df_ed["Nequi_Real"].sum()
                    v_tarj = df_ed["Tarjeta_Real"].sum()

                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Venta Auditada", formato_moneda(v_total))
                    c2.metric("Efectivo Real", formato_moneda(v_efec))
                    c3.metric("Nequi Real", formato_moneda(v_nequi))
                    c4.metric("Tarjeta Real", formato_moneda(v_tarj))

                    # Comparar contra lo que se grabó en el cierre original
                    teo_original = float(limpiar_numero(cierre_sel.get('Saldo_Teorico_E', 0)))
                    st.write(f"Venta en Efectivo reportada originalmente: **{formato_moneda(teo_original)}**")
                    
                    if v_efec != teo_original:
                        st.warning(f"Diferencia detectada en auditoría: {formato_moneda(v_efec - teo_original)}")
                    else:
                        st.success("La auditoría coincide con el efectivo reportado originalmente.")

                else:
                    st.error("No se encontraron los tickets en la base de datos de ventas.")
        except Exception as e:
            st.error(f"Error procesando la auditoría: {e}")

    # Botón Actualizar
    st.markdown("---")
    if st.button("🔄 RECARGAR DATOS"):
        st.cache_data.clear()
        st.rerun()
