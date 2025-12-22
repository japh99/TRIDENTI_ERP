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

# Estructura Maestra Obligatoria
HEADERS_CIERRE = [
    "Fecha_Cierre", "Hora_Cierre", "Saldo_Teorico_E", "Saldo_Real_Cor", 
    "Diferencia", "Total_Nequi", "Total_Tarjetas", "Ticket_Ini", "Ticket_Fin",
    "Profit_Retenido", "Estado_Ahorro", "Numero_Cierre_Loyverse", "Shift_ID"
]

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

# --- FUNCIONES DE BLINDAJE Y CARGA ---

def asegurar_estructura_log(ws):
    """Repara el Excel si faltan columnas o están mal escritas."""
    try:
        actuales = [c.strip() for c in ws.row_values(1)]
        if not actuales or actuales[0] == "":
            ws.update('A1', [HEADERS_CIERRE])
            return
        
        faltantes = [c for c in HEADERS_CIERRE if c not in actuales]
        if faltantes:
            next_col = len(actuales) + 1
            for col in faltantes:
                ws.update_cell(1, prox_col, col)
                prox_col += 1
    except: pass

def cargar_pool_tickets(sheet):
    """Sincronización con Ventas: Agrupa productos por ticket y maneja madrugada."""
    try:
        ws_v = sheet.worksheet(HOJA_VENTAS)
        df_raw = leer_datos_seguro(ws_v)
        if df_raw.empty: return pd.DataFrame()

        df_raw.columns = df_raw.columns.str.strip()
        df_raw["Total_Dinero"] = pd.to_numeric(df_raw["Total_Dinero"], errors='coerce').fillna(0)
        
        # Consolidación por Recibo
        df_tickets = df_raw.groupby("Numero_Recibo").agg({
            "Hora": "first", "Fecha": "first", "Total_Dinero": "sum",
            "Metodo_Pago_Loyverse": "first", "Shift_ID": "first"
        }).reset_index()
        
        # Orden cronológico real para madrugada
        df_tickets["TS"] = pd.to_datetime(df_tickets["Fecha"] + " " + df_tickets["Hora"], errors='coerce')
        return df_tickets.sort_values("TS", ascending=False).drop(columns=["TS"])
    except: return pd.DataFrame()

# --- INTERFAZ ---

def show(sheet):
    st.title("🔐 Tesorería, Auditoría & Banco Profit")
    
    if not sheet: return
    ws_c = sheet.worksheet(HOJA_CIERRES)
    asegurar_estructura_log(ws_c)

    t1, t2, t3 = st.tabs(["📝 PROCESAR CIERRE", "📜 HISTORIAL", "📊 DASHBOARD"])

    with t1:
        st.subheader("Nuevo Arqueo del Turno")
        df_pool = cargar_pool_tickets(sheet)
        
        if df_pool.empty:
            st.warning("No hay ventas sincronizadas. Ve al módulo de Ventas.")
        else:
            # Selector de Rango de Tickets
            opciones = df_pool.apply(lambda x: f"#{x['Numero_Recibo']} | {x['Fecha']} {x['Hora']} | {formato_moneda(x['Total_Dinero'])}", axis=1).tolist()
            
            c1, c2 = st.columns(2)
            with c1: t_fin_sel = st.selectbox("Ticket de CIERRE (Último):", opciones, index=0)
            with c2: t_ini_sel = st.selectbox("Ticket de APERTURA (Primero):", opciones, index=min(len(opciones)-1, 15))

            id_ini = t_ini_sel.split(" | ")[0].replace("#", "")
            id_fin = t_fin_sel.split(" | ")[0].replace("#", "")

            # Obtener el bloque del turno
            idx_i = df_pool[df_pool["Numero_Recibo"] == id_ini].index[0]
            idx_f = df_pool[df_pool["Numero_Recibo"] == id_fin].index[0]
            start, end = (idx_i, idx_f) if idx_i > idx_f else (idx_f, idx_i)
            df_turno = df_pool.loc[end:start].copy()

            # --- AUDITORÍA Y PAGOS MIXTOS ---
            with st.expander("🛠️ Auditoría de Pagos del Turno", expanded=True):
                df_turno["Efectivo_Real"] = df_turno.apply(lambda x: x["Total_Dinero"] if x["Metodo_Pago_Loyverse"] == "Efectivo" else 0.0, axis=1)
                df_turno["Nequi_Real"] = df_turno.apply(lambda x: x["Total_Dinero"] if "Nequi" in str(x["Metodo_Pago_Loyverse"]) else 0.0, axis=1)
                df_turno["Tarjeta_Real"] = df_turno.apply(lambda x: x["Total_Dinero"] if "Tarjeta" in str(x["Metodo_Pago_Loyverse"]) else 0.0, axis=1)
                df_turno["Validación"] = df_turno["Efectivo_Real"] + df_turno["Nequi_Real"] + df_turno["Tarjeta_Real"]

                df_ed = st.data_editor(
                    df_turno[["Numero_Recibo", "Hora", "Total_Dinero", "Efectivo_Real", "Nequi_Real", "Tarjeta_Real", "Validación"]],
                    column_config={
                        "Total_Dinero": st.column_config.NumberColumn("Valor Ticket", format="$%d", disabled=True),
                        "Validación": st.column_config.NumberColumn("Suma", format="$%d", disabled=True),
                    },
                    hide_index=True, use_container_width=True, key="editor_teso_final_pro"
                )
                
                check_suma = abs(df_ed["Total_Dinero"] - df_ed["Validación"]).sum()
                if check_suma > 1: st.error("🚨 La suma de los pagos no coincide con el total de los tickets.")

            # --- SINCRONIZACIÓN CON GASTOS ---
            try:
                ws_g = sheet.worksheet(HOJA_GASTOS)
                df_g = leer_datos_seguro(ws_g)
                df_g.columns = df_g.columns.str.strip()
                # Rango horario del turno
                h_inicio = df_turno["Hora"].iloc[-1]
                h_fin = df_turno["Hora"].iloc[0]
                f_turno = df_turno["Fecha"].iloc[0]
                
                mask_g = (df_g["Fecha"] == f_turno) & (df_g["Metodo_Pago"].str.contains("Efectivo", na=False))
                total_gastos_caja = pd.to_numeric(df_g[mask_g]["Monto"], errors='coerce').sum()
            except: total_gastos_caja = 0.0

            # CÁLCULOS
            v_total = df_ed["Total_Dinero"].sum()
            v_efec_bruto = df_ed["Efectivo_Real"].sum()
            saldo_teo_efectivo = v_efec_bruto - total_gastos_caja

            st.markdown("---")
            k1, k2, k3 = st.columns(3)
            k1.metric("Ingreso Efectivo", formato_moneda(v_efec_bruto))
            k2.metric("Gastos Pagados Turno", f"- {formato_moneda(total_gastos_caja)}")
            k3.metric("(=) DEBE HABER CAJA", formato_moneda(saldo_teo_efectivo))

            # ARQUEO Y SEMÁFORO
            c_real, c_z = st.columns(2)
            real = c_real.number_input("¿Efectivo físico contado?", min_value=0.0, step=500.0)
            z_rep = c_z.text_input("Z-Report #")
            
            diff = real - saldo_teo_efectivo
            if diff == 0: st.success("✅ CAJA CUADRADA")
            elif diff > 0: st.info(f"🔵 SOBRANTE: {formato_moneda(diff)}")
            else: st.error(f"🔴 FALTANTE: {formato_moneda(diff)}")

            # BANCO PROFIT: CALCULO Y SEÑAL
            st.markdown("---")
            pct = st.slider("% Ahorro (Profit First)", 1, 15, 5)
            monto_ahorro = v_total * (pct / 100)
            st.warning(f"🐷 Reserva para el Banco: {formato_moneda(monto_ahorro)} (Estado: PENDIENTE)")

            if st.button("🔒 GUARDAR CIERRE DEFINITIVO", type="primary", use_container_width=True):
                if check_suma > 1: st.warning("Corrige los tickets en rojo.")
                elif not z_rep: st.warning("Falta número de Z-Report.")
                else:
                    datos_finales = {
                        "Fecha_Cierre": str(df_turno["Fecha"].iloc[-1]),
                        "Hora_Cierre": datetime.now(ZONA_HORARIA).strftime("%H:%M"),
                        "Saldo_Teorico_E": saldo_teo_efectivo,
                        "Saldo_Real_Cor": real,
                        "Diferencia": diff,
                        "Total_Nequi": df_ed["Nequi_Real"].sum(),
                        "Total_Tarjetas": df_ed["Tarjeta_Real"].sum(),
                        "Ticket_Ini": id_ini,
                        "Ticket_Fin": id_fin,
                        "Profit_Retenido": monto_ahorro,
                        "Estado_Ahorro": "Pendiente", # SEÑAL PARA EL BANCO
                        "Numero_Cierre_Loyverse": z_rep,
                        "Shift_ID": str(df_turno["Shift_ID"].iloc[0])
                    }
                    header_excel = [c.strip() for c in ws_c.row_values(1)]
                    fila_subir = [str(datos_finales.get(h, "")) for h in header_excel]
                    ws_c.append_row(fila_subir)
                    st.cache_data.clear()
                    st.balloons(); time.sleep(1); st.rerun()

    with t2:
        st.subheader("📜 Historial de Cierres")
        if st.button("🔄 ACTUALIZAR DATOS"):
            st.cache_data.clear(); st.rerun()
        
        df_h = leer_datos_seguro(sheet.worksheet(HOJA_CIERRES))
        if not df_h.empty:
            df_h.columns = df_h.columns.str.strip()
            # COMPATIBILIDAD DE COLUMNA DE FECHA
            col_sort = "Fecha_Cierre" if "Fecha_Cierre" in df_h.columns else df_h.columns[0]
            df_h = df_h.sort_values(col_sort, ascending=False).head(20)
            
            # Formatear moneda en tabla
            cols_money = ["Saldo_Teorico_E", "Saldo_Real_Cor", "Diferencia", "Profit_Retenido"]
            for col in cols_money:
                if col in df_h.columns:
                    df_h[col] = pd.to_numeric(df_h[col], errors='coerce').apply(formato_moneda)
            st.dataframe(df_h, use_container_width=True, hide_index=True)

    with t3:
        st.subheader("📊 Dashboard Gerencial")
        df_dash = leer_datos_seguro(sheet.worksheet(HOJA_CIERRES))
        if not df_dash.empty:
            df_dash.columns = df_dash.columns.str.strip()
            df_dash["Saldo_Real_Cor"] = pd.to_numeric(df_dash["Saldo_Real_Cor"], errors='coerce').fillna(0)
            st.metric("Efectivo Neto Total (Histórico)", formato_moneda(df_dash["Saldo_Real_Cor"].sum()))
            fig = px.bar(df_dash, x=col_sort, y="Saldo_Real_Cor", title="Ingresos de Efectivo por Fecha", color_discrete_sequence=['#c5a065'])
            st.plotly_chart(fig, use_container_width=True)
