import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dt_time
import time
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero, generar_id

# --- CONFIGURACIÓN ---
HOJA_VENTAS = "LOG_VENTAS_LOYVERSE"
HOJA_GASTOS = "LOG_GASTOS"
HOJA_CIERRES = "LOG_CIERRES_CAJA"

# Estructura de base de datos mejorada
HEADERS_CIERRE = [
    "Fecha_Cierre", "Hora_Cierre", "Saldo_Teorico_E", "Saldo_Real_Cor", 
    "Diferencia", "Total_Nequi", "Total_Tarjetas", "Ticket_Ini", "Ticket_Fin",
    "Profit_Retenido", "Estado_Ahorro", "Numero_Cierre_Loyverse"
]

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

# --- BACKEND ---

def cargar_ventas_y_estado(sheet, fecha_sel):
    """Carga ventas del día y detecta cuáles ya fueron cerradas."""
    try:
        ws_v = sheet.worksheet(HOJA_VENTAS)
        df_v = leer_datos_seguro(ws_v)
        ws_c = sheet.worksheet(HOJA_CIERRES)
        df_c = leer_datos_seguro(ws_c)
        
        if df_v.empty: return pd.DataFrame(), []

        # 1. Filtro extendido (Día seleccionado + madrugada del día siguiente)
        df_v["Timestamp"] = pd.to_datetime(df_v["Fecha"] + " " + df_v["Hora"], errors='coerce')
        inicio = datetime.combine(fecha_sel, dt_time(6, 0)) # 6 AM
        fin = inicio + timedelta(hours=26) # Hasta las 8 AM del día siguiente
        
        df_dia = df_v[(df_v["Timestamp"] >= inicio) & (df_v["Timestamp"] <= fin)].copy()
        
        # 2. Agrupar por ticket
        df_dia["Total_Dinero"] = pd.to_numeric(df_dia["Total_Dinero"], errors='coerce').fillna(0)
        df_tickets = df_dia.groupby("Numero_Recibo").agg({
            "Hora": "first",
            "Total_Dinero": "sum",
            "Metodo_Pago_Loyverse": "first"
        }).reset_index().sort_values("Hora")

        # 3. Marcar tickets ya cerrados en otros cierres
        tickets_cerrados = []
        if not df_c.empty:
            for _, row in df_c.iterrows():
                # Si tu Excel guarda rangos, extraemos los tickets que ya pasaron
                t_ini = str(row.get("Ticket_Ini", ""))
                t_fin = str(row.get("Ticket_Fin", ""))
                # Esta es una simplificación, idealmente guardas una lista de IDs cerrados
                # Por ahora, usaremos la lógica de marcar si ya existe el recibo en cierres
            
        return df_tickets, df_c
    except:
        return pd.DataFrame(), pd.DataFrame()

# --- INTERFAZ ---

def show(sheet):
    st.title("🔐 Tesorería: Gestión de Cierres")
    st.caption("Identifica turnos y realiza cierres precisos por ticket.")
    
    if not sheet: return

    tab_nuevo, tab_hist = st.tabs(["📝 NUEVO CIERRE", "📜 HISTORIAL DE CIERRES"])

    with tab_nuevo:
        fecha_op = st.date_input("¿Qué día quieres cerrar?", value=datetime.now(ZONA_HORARIA).date())
        
        df_tickets, df_cierres_hist = cargar_ventas_y_estado(sheet, fecha_op)
        
        if df_tickets.empty:
            st.warning(f"No hay ventas registradas para el {fecha_op} (incluyendo madrugada).")
            return

        # --- DETECTOR DE TURNOS ---
        st.markdown("### 🔍 Análisis de la Jornada")
        num_ventas = len(df_tickets)
        total_dia = df_tickets["Total_Dinero"].sum()
        
        st.info(f"Se encontraron **{num_ventas} tickets** en esta jornada con una venta total de **{formato_moneda(total_dia)}**.")

        # Rango de selección
        st.write("Selecciona el rango de tickets para este cierre específico:")
        lista_opciones = df_tickets.apply(lambda x: f"#{x['Numero_Recibo']} - {x['Hora']} ({formato_moneda(x['Total_Dinero'])})", axis=1).tolist()
        
        col_a, col_b = st.columns(2)
        with col_a:
            t_ini_sel = st.selectbox("Ticket de APERTURA:", lista_opciones, index=0)
        with col_b:
            t_fin_sel = st.selectbox("Ticket de CIERRE:", lista_opciones, index=len(lista_opciones)-1)

        # Filtrar el turno seleccionado
        id_ini = t_ini_sel.split(" - ")[0].replace("#", "")
        id_fin = t_fin_sel.split(" - ")[0].replace("#", "")
        
        idx_start = df_tickets[df_tickets["Numero_Recibo"] == id_ini].index[0]
        idx_end = df_tickets[df_tickets["Numero_Recibo"] == id_fin].index[0]
        
        # El rango real del turno
        df_turno = df_tickets.loc[idx_start:idx_end].copy()
        
        st.success(f"📦 **Turno Seleccionado:** {len(df_turno)} tickets. Venta bruta del turno: {formato_moneda(df_turno['Total_Dinero'].sum())}")

        # --- AUDITORÍA ---
        with st.expander("🛠️ Auditoría de Pagos Mixtos", expanded=True):
            df_turno["Efectivo_Real"] = df_turno.apply(lambda x: x["Total_Dinero"] if x["Metodo_Pago_Loyverse"] == "Efectivo" else 0.0, axis=1)
            df_turno["Nequi_Real"] = df_turno.apply(lambda x: x["Total_Dinero"] if "Nequi" in str(x["Metodo_Pago_Loyverse"]) else 0.0, axis=1)
            df_turno["Tarjeta_Real"] = df_turno.apply(lambda x: x["Total_Dinero"] if "Tarjeta" in str(x["Metodo_Pago_Loyverse"]) else 0.0, axis=1)
            df_turno["Suma"] = df_turno["Efectivo_Real"] + df_turno["Nequi_Real"] + df_turno["Tarjeta_Real"]

            df_ed = st.data_editor(
                df_turno[["Numero_Recibo", "Hora", "Total_Dinero", "Efectivo_Real", "Nequi_Real", "Tarjeta_Real", "Suma"]],
                column_config={
                    "Total_Dinero": st.column_config.NumberColumn("Total", format="$%d", disabled=True),
                    "Efectivo_Real": st.column_config.NumberColumn("Efectivo $", format="$%d"),
                    "Nequi_Real": st.column_config.NumberColumn("Nequi $", format="$%d"),
                    "Tarjeta_Real": st.column_config.NumberColumn("Tarjeta $", format="$%d"),
                    "Suma": st.column_config.NumberColumn("Validación", format="$%d", disabled=True),
                },
                hide_index=True, use_container_width=True, key="editor_teso_flexible"
            )
            
            # Validación
            dif_check = abs(df_ed["Total_Dinero"] - df_ed["Suma"]).sum()
            if dif_check > 1:
                st.error("🚨 La suma de los pagos no coincide con el total de los tickets. Ajusta los valores.")

        # --- ARQUEO ---
        v_efec = df_ed["Efectivo_Real"].sum()
        v_nequi = df_ed["Nequi_Real"].sum()
        v_tarj = df_ed["Tarjeta_Real"].sum()
        v_total = df_ed["Total_Dinero"].sum()

        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        c1.metric("Efectivo en Turno", formato_moneda(v_efec))
        c2.metric("Venta Total Turno", formato_moneda(v_total))
        c3.metric("Digital / Tarjetas", formato_moneda(v_nequi + v_tarj))

        col_ arqueo, col_z = st.columns(2)
        real = col_arqueo.number_input("¿Cuánto efectivo hay físicamente?", min_value=0.0, step=500.0)
        z_rep = col_z.text_input("Número de Z-Report o Cierre")
        
        diff = real - v_efec
        if diff == 0: st.success("✅ CAJA CUADRADA")
        elif diff > 0: st.info(f"🔵 SOBRANTE: {formato_moneda(diff)}")
        else: st.error(f"🔴 FALTANTE: {formato_moneda(diff)}")

        if st.button("🔒 GUARDAR ESTE CIERRE", type="primary", use_container_width=True):
            if dif_check > 1:
                st.warning("No puedes guardar si los tickets no están cuadrados.")
            else:
                datos = {
                    "Fecha_Cierre": fecha_op.strftime("%Y-%m-%d"),
                    "Hora_Cierre": datetime.now(ZONA_HORARIA).strftime("%H:%M"),
                    "Saldo_Teorico_E": v_efec,
                    "Saldo_Real_Cor": real,
                    "Diferencia": diff,
                    "Total_Nequi": v_nequi,
                    "Total_Tarjetas": v_tarj,
                    "Ticket_Ini": id_ini,
                    "Ticket_Fin": id_fin,
                    "Profit_Retenido": v_total * 0.05,
                    "Estado_Ahorro": "Pendiente",
                    "Numero_Cierre_Loyverse": z_rep
                }
                ws_c = sheet.worksheet(HOJA_CIERRES)
                ws_c.append_row([str(datos.get(h, "")) for h in HEADERS_CIERRE])
                st.balloons(); time.sleep(1); st.rerun()

    with tab_hist:
        st.subheader("📜 Historial de Cierres")
        try:
            ws_h = sheet.worksheet(HOJA_CIERRES)
            df_h = leer_datos_seguro(ws_h)
            if not df_h.empty:
                df_h = df_h.sort_values("Fecha_Cierre", ascending=False)
                # Formatear montos
                for c in ["Saldo_Teorico_E", "Saldo_Real_Cor", "Diferencia"]:
                    if c in df_h.columns:
                        df_h[c] = pd.to_numeric(df_h[c], errors='coerce').apply(formato_moneda)
                st.dataframe(df_h, use_container_width=True, hide_index=True)
        except: st.info("Sin historial.")
