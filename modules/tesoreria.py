import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta, date, time as dt_time
import time
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero, generar_id

# --- CONFIGURACIÓN DE HOJAS ---
HOJA_VENTAS = "LOG_VENTAS_LOYVERSE"
HOJA_GASTOS = "LOG_GASTOS"
HOJA_CIERRES = "LOG_CIERRES_CAJA"

# Estructura Maestra (Headers exactos para evitar errores)
HEADERS_CIERRE = [
    "Fecha_Cierre", "Hora_Cierre", "Saldo_Teorico_E", "Saldo_Real_Cor", 
    "Diferencia", "Total_Nequi", "Total_Tarjetas", "Ticket_Ini", "Ticket_Fin",
    "Profit_Retenido", "Estado_Ahorro", "Numero_Cierre_Loyverse", "Shift_ID"
]

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

# --- FUNCIONES DE SEGURIDAD Y CARGA ---

def asegurar_estructura_log(ws):
    """Blindaje: Revisa y repara las columnas del Excel de cierres."""
    try:
        columnas_actuales = ws.row_values(1)
        if not columnas_actuales:
            ws.update('A1', [HEADERS_CIERRE])
            return
        # Limpiar espacios en los encabezados del Excel
        columnas_actuales = [c.strip() for c in columnas_actuales]
        faltantes = [c for c in HEADERS_CIERRE if c not in columnas_actuales]
        if faltantes:
            # Si faltan columnas, las agregamos al final para no romper nada
            prox_col = len(columnas_actuales) + 1
            for col in faltantes:
                ws.update_cell(1, prox_col, col)
                prox_col += 1
    except: pass

def cargar_jornada_operativa(sheet, fecha_base):
    """
    MANEJO DE MADRUGADA: Filtra de 6 AM a 6 AM del día siguiente.
    SINCRONIZACIÓN CON VENTAS: Agrupa por Ticket.
    """
    try:
        # 1. CARGAR VENTAS
        ws_v = sheet.worksheet(HOJA_VENTAS)
        df_v = leer_datos_seguro(ws_v)
        if df_v.empty: return pd.DataFrame(), pd.DataFrame(), 0.0
        
        # Limpiar nombres de columnas
        df_v.columns = df_v.columns.str.strip()
        
        # Crear tiempo real (Manejo de Madrugada)
        df_v["TS"] = pd.to_datetime(df_v["Fecha"] + " " + df_v["Hora"], errors='coerce')
        df_v = df_v.dropna(subset=["TS"])
        
        inicio_j = datetime.combine(fecha_base, dt_time(6, 0))
        fin_j = inicio_j + timedelta(hours=24)
        
        df_dia = df_v[(df_v["TS"] >= inicio_j) & (df_v["TS"] < fin_j)].copy()
        if df_dia.empty: return pd.DataFrame(), pd.DataFrame(), 0.0

        df_dia["Total_Dinero"] = pd.to_numeric(df_dia["Total_Dinero"], errors='coerce').fillna(0)

        # AGRUPAR PRODUCTOS POR TICKET
        df_tickets = df_dia.groupby("Numero_Recibo").agg({
            "Hora": "first",
            "Total_Dinero": "sum",
            "Metodo_Pago_Loyverse": "first",
            "Shift_ID": "first"
        }).reset_index().sort_values("Hora")

        # 2. CARGAR GASTOS (SINCRONIZACIÓN CON GASTOS)
        ws_g = sheet.worksheet(HOJA_GASTOS)
        df_g = leer_datos_seguro(ws_g)
        gastos_efectivo = 0.0
        df_g_det = pd.DataFrame()
        
        if not df_g.empty:
            df_g.columns = df_g.columns.str.strip()
            df_g["TS"] = pd.to_datetime(df_g["Fecha"] + " " + df_g["Hora"], errors='coerce')
            mask_g = (df_g["TS"] >= inicio_j) & (df_g["TS"] < fin_j) & (df_g["Metodo_Pago"].str.contains("Efectivo", na=False))
            df_g_det = df_g[mask_g].copy()
            gastos_efectivo = pd.to_numeric(df_g_det["Monto"], errors='coerce').sum()

        return df_tickets, df_g_det, gastos_efectivo
    except Exception as e:
        st.error(f"Error en carga operativa: {e}")
        return pd.DataFrame(), pd.DataFrame(), 0.0

# --- INTERFAZ ---

def show(sheet):
    st.title("🔐 Tesorería: Cierre & Auditoría")
    
    if not sheet: return
    ws_cierres = sheet.worksheet(HOJA_CIERRES)
    asegurar_estructura_log(ws_cierres) # Reparación automática

    t1, t2, t3 = st.tabs(["📝 PROCESAR CIERRE", "📜 HISTORIAL", "📊 DASHBOARD"])

    with t1:
        st.subheader("Cuadre de Turno (6 AM - 6 AM)")
        fecha_sel = st.date_input("¿Qué día abrió caja?", value=date.today())
        
        df_tickets, df_g_det, total_gastos_caja = cargar_jornada_operativa(sheet, fecha_sel)
        
        if df_tickets.empty:
            st.warning(f"No hay ventas registradas para la jornada del {fecha_sel}.")
        else:
            # --- HISTORIAL Y AUDITORÍA: REPARTIR PAGOS ---
            with st.expander("🛠️ Auditoría de Tickets y Pagos Mixtos", expanded=True):
                st.write("Ajusta las columnas si el pago fue repartido (Efectivo/Nequi/Tarjeta).")
                
                df_tickets["Efectivo_Real"] = df_tickets.apply(lambda x: x["Total_Dinero"] if x["Metodo_Pago_Loyverse"] == "Efectivo" else 0.0, axis=1)
                df_tickets["Nequi_Real"] = df_tickets.apply(lambda x: x["Total_Dinero"] if "Nequi" in str(x["Metodo_Pago_Loyverse"]) else 0.0, axis=1)
                df_tickets["Tarjeta_Real"] = df_tickets.apply(lambda x: x["Total_Dinero"] if "Tarjeta" in str(x["Metodo_Pago_Loyverse"]) else 0.0, axis=1)
                df_tickets["Suma"] = df_tickets["Efectivo_Real"] + df_tickets["Nequi_Real"] + df_tickets["Tarjeta_Real"]

                df_ed = st.data_editor(
                    df_tickets[["Numero_Recibo", "Hora", "Total_Dinero", "Efectivo_Real", "Nequi_Real", "Tarjeta_Real", "Suma"]],
                    column_config={
                        "Total_Dinero": st.column_config.NumberColumn("Valor Ticket", format="$%d", disabled=True),
                        "Suma": st.column_config.NumberColumn("Validación", format="$%d", disabled=True),
                        "Numero_Recibo": "Recibo #"
                    },
                    hide_index=True, use_container_width=True, key="editor_teso_pro"
                )
                
                check_suma = abs(df_ed["Total_Dinero"] - df_ed["Suma"]).sum()
                if check_suma > 1:
                    st.error("🚨 La validación de suma de tickets no coincide. Revisa los montos en rojo.")

            # --- CÁLCULOS DINÁMICOS ---
            v_total = df_ed["Total_Dinero"].sum()
            v_efec_bruto = df_ed["Efectivo_Real"].sum()
            v_nequi = df_ed["Nequi_Real"].sum()
            v_tarj = df_ed["Tarjeta_Real"].sum()
            
            # Sincronización con Gastos
            saldo_teo_efectivo = v_efec_bruto - total_gastos_caja

            st.markdown("#### 📊 Resumen Auditado del Turno")
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Venta Bruta", formato_moneda(v_total))
            k2.metric("Efectivo en Caja", formato_moneda(v_efec_bruto))
            k3.metric("Nequi", formato_moneda(v_nequi))
            k4.metric("Tarjetas", formato_moneda(v_tarj))

            st.markdown("---")
            st.markdown("#### 💵 Arqueo de Efectivo Físico")
            a1, a2, a3 = st.columns(3)
            a1.metric("(+) Efectivo Ventas", formato_moneda(v_efec_bruto))
            a2.metric("(-) Gastos en Efectivo", f"- {formato_moneda(total_gastos_caja)}")
            a3.metric("(=) DEBE HABER EN CAJA", formato_moneda(saldo_teo_efectivo))

            c_cont, c_z = st.columns(2)
            real = c_cont.number_input("¿Cuánto efectivo hay físicamente?", min_value=0.0, step=500.0)
            z_rep = c_z.text_input("Z-Report / Número de Cierre")
            
            diff = real - saldo_teo_efectivo
            if diff == 0: st.success("✅ CAJA CUADRADA")
            elif diff > 0: st.info(f"🔵 SOBRANTE: {formato_moneda(diff)}")
            else: st.error(f"🔴 FALTANTE: {formato_moneda(diff)}")

            # --- BANCO PROFIT: EL CÁLCULO Y LA SEÑAL ---
            st.markdown("---")
            st.markdown("### 🐷 Reserva para Banco Profit")
            pct = st.slider("% Ahorro Sugerido:", 1, 15, 5)
            monto_ahorro = v_total * (pct / 100)
            st.warning(f"Debes separar **{formato_moneda(monto_ahorro)}** para el fondo de ahorro.")

            if st.button("🔒 GUARDAR CIERRE DEFINITIVO", type="primary", use_container_width=True):
                if check_suma > 1:
                    st.warning("No puedes guardar con tickets descuadrados.")
                elif not z_rep:
                    st.warning("Debes ingresar el número de Z-Report.")
                else:
                    # CERO ERRORES DE COLUMNA: Mapear datos según HEADERS_CIERRE
                    datos_finales = {
                        "Fecha_Cierre": str(fecha_sel),
                        "Hora_Cierre": datetime.now(ZONA_HORARIA).strftime("%H:%M"),
                        "Saldo_Teorico_E": saldo_teo_efectivo,
                        "Saldo_Real_Cor": real,
                        "Diferencia": diff,
                        "Total_Nequi": v_nequi,
                        "Total_Tarjetas": v_tarj,
                        "Ticket_Ini": df_ed["Numero_Recibo"].iloc[0],
                        "Ticket_Fin": df_ed["Numero_Recibo"].iloc[-1],
                        "Profit_Retenido": monto_ahorro,
                        "Estado_Ahorro": "Pendiente", # LA SEÑAL PARA BANCO PROFIT
                        "Numero_Cierre_Loyverse": z_rep,
                        "Shift_ID": str(df_tickets["Shift_ID"].iloc[0])
                    }
                    
                    # Organizar fila según el Excel real (por si cambiaron de lugar las columnas)
                    header_excel = ws_cierres.row_values(1)
                    fila_subir = [str(datos_finales.get(h.strip(), "")) for h in header_excel]
                    
                    ws_cierres.append_row(fila_subir)
                    st.balloons()
                    time.sleep(1)
                    st.rerun()

    with t2:
        st.subheader("📜 Historial de Cierres")
        if st.button("🔄 ACTUALIZAR DATOS"):
            st.cache_data.clear(); st.rerun()
            
        df_h = leer_datos_seguro(sheet.worksheet(HOJA_CIERRES))
        if not df_h.empty:
            df_h.columns = df_h.columns.str.strip() # Limpieza de espacios
            df_h = df_h.sort_values("Fecha_Cierre", ascending=False).head(20)
            
            # Formatear moneda en la tabla
            for col in ["Saldo_Real_Cor", "Diferencia", "Profit_Retenido"]:
                if col in df_h.columns:
                    df_h[col] = pd.to_numeric(df_h[col], errors='coerce').apply(formato_moneda)
            
            st.dataframe(df_h, use_container_width=True, hide_index=True)

    with t3:
        st.subheader("📊 Dashboard de Ingresos Netos")
        df_dash = leer_datos_seguro(sheet.worksheet(HOJA_CIERRES))
        if not df_dash.empty:
            df_dash.columns = df_dash.columns.str.strip()
            df_dash["Saldo_Real_Cor"] = pd.to_numeric(df_dash["Saldo_Real_Cor"], errors='coerce').fillna(0)
            df_dash["Total_Nequi"] = pd.to_numeric(df_dash["Total_Nequi"], errors='coerce').fillna(0)
            
            # Gráfico de composición
            total_efec = df_dash["Saldo_Real_Cor"].sum()
            total_digi = df_dash["Total_Nequi"].sum()
            
            fig = px.pie(names=["Efectivo Neto", "Digital (Nequi)"], values=[total_efec, total_digi], 
                         hole=0.5, color_discrete_sequence=["#c5a065", "#580f12"])
            st.plotly_chart(fig, use_container_width=True)
            
            st.metric("Total Efectivo en Caja (Acumulado)", formato_moneda(total_efec))
