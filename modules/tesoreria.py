import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import time
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero

# --- CONFIGURACIÓN ---
HOJA_VENTAS = "LOG_VENTAS_LOYVERSE"
HOJA_GASTOS = "LOG_PAGOS_GASTOS"
HOJA_CIERRES = "LOG_CIERRES_CAJA"

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

def show(sheet):
    st.title("🔐 Tesorería: Auditoría Maestra de Cierres")
    st.caption("Sincronización total basada en Turnos (Shifts) con desglose de pagos.")

    # 1. CARGA DE DATOS SIN FILTROS (Para no perder días)
    try:
        df_v = leer_datos_seguro(sheet.worksheet(HOJA_VENTAS))
        df_g = leer_datos_seguro(sheet.worksheet(HOJA_GASTOS))
        df_c = leer_datos_seguro(sheet.worksheet(HOJA_CIERRES))
    except:
        st.error("Error conectando con la base de datos.")
        return

    if df_v.empty:
        st.warning("No hay datos de ventas. Escanea cierres en el módulo de Ventas primero.")
        return

    col_id = "Shift_ID"

    tab_audit, tab_hist, tab_dash = st.tabs(["🔎 AUDITAR TURNO", "📜 HISTORIAL", "📊 DASHBOARD"])

    with tab_audit:
        # --- LÓGICA DE FECHAS ROBUSTA (IGUAL A VENTAS) ---
        df_v["Fecha_DT"] = pd.to_datetime(df_v["Fecha"], errors='coerce')
        df_v = df_v.dropna(subset=["Fecha_DT"])
        df_v = df_v.sort_values(["Fecha_DT", "Hora"], ascending=[False, False])
        
        # Identificar turnos ya auditados en Tesorería
        auditados = []
        if not df_c.empty and "Numero_Cierre_Loyverse" in df_c.columns:
            auditados = df_c["Numero_Cierre_Loyverse"].astype(str).str.strip().unique().tolist()
        
        # Limpiar Shift_ID
        df_v[col_id] = df_v[col_id].astype(str).str.strip()
        
        # Filtrar turnos únicos que faltan por auditar
        df_pendientes = df_v[~df_v[col_id].isin(auditados)].copy()

        if df_pendientes.empty:
            st.success("🎉 ¡Felicidades! Todos los turnos descargados han sido auditados.")
        else:
            # --- SELECTOR DE MES (IDÉNTICO A VENTAS) ---
            df_pendientes["Mes_Label"] = df_pendientes["Fecha_DT"].dt.strftime('%m - %Y')
            meses_disp = sorted(df_pendientes["Mes_Label"].unique().tolist(), reverse=True)
            
            c_mes, c_turno = st.columns([1, 2])
            mes_sel = c_mes.selectbox("Filtrar por Mes:", meses_disp)
            
            # Turnos del mes seleccionado
            df_mes = df_pendientes[df_pendientes["Mes_Label"] == mes_sel]
            df_v["Total_Dinero"] = pd.to_numeric(df_v["Total_Dinero"], errors='coerce').fillna(0)
            
            # Crear lista de opciones para el selectbox
            opciones_turnos = []
            mapeo_ids = []
            
            for sid in df_mes[col_id].unique():
                if sid == "nan" or not sid: continue
                data_s = df_v[df_v[col_id] == sid]
                fecha_s = data_s["Fecha"].iloc[0]
                total_s = data_s["Total_Dinero"].sum()
                opciones_turnos.append(f"{fecha_s} | Venta: {formato_moneda(total_s)} | ID: {sid[:6]}")
                mapeo_ids.append(sid)

            seleccion_label = c_turno.selectbox("📋 Selecciona el Cierre a auditar:", opciones_turnos)
            
            if seleccion_label:
                shift_id_real = mapeo_ids[opciones_turnos.index(seleccion_label)]
                df_sel = df_v[df_v[col_id] == shift_id_real].copy()
                fecha_turno = df_sel["Fecha"].iloc[0]

                st.markdown(f"### 🛡️ Auditando Turno: `{shift_id_real}`")

                # --- EDITOR DE TICKETS (SOLUCIÓN A PAGOS COMBINADOS) ---
                st.markdown("#### 🎫 Desglose Manual de Pagos por Ticket")
                st.info("💡 Haz doble clic en las celdas para repartir el dinero si el pago fue combinado.")

                # Agrupamos por ticket
                df_tickets = df_sel.groupby("Numero_Recibo").agg({
                    "Total_Dinero": "sum",
                    "Metodo_Pago_Real_Auditado": "first"
                }).reset_index()

                # Columnas de edición manual
                df_tickets["Efectivo_R"] = df_tickets.apply(lambda x: x["Total_Dinero"] if x["Metodo_Pago_Real_Auditado"] == "Efectivo" else 0.0, axis=1)
                df_tickets["Nequi_R"] = df_tickets.apply(lambda x: x["Total_Dinero"] if x["Metodo_Pago_Real_Auditado"] == "Nequi" else 0.0, axis=1)
                df_tickets["Tarjeta_R"] = df_tickets.apply(lambda x: x["Total_Dinero"] if x["Metodo_Pago_Real_Auditado"] == "Tarjeta" else 0.0, axis=1)

                df_editado = st.data_editor(
                    df_tickets[["Numero_Recibo", "Total_Dinero", "Efectivo_R", "Nequi_R", "Tarjeta_R"]],
                    column_config={
                        "Numero_Recibo": st.column_config.TextColumn("Ticket #", disabled=True),
                        "Total_Dinero": st.column_config.NumberColumn("Valor Ticket", format="$%d", disabled=True),
                        "Efectivo_R": st.column_config.NumberColumn("Efectivo ($)", min_value=0.0, format="$%d"),
                        "Nequi_R": st.column_config.NumberColumn("Nequi ($)", min_value=0.0, format="$%d"),
                        "Tarjeta_R": st.column_config.NumberColumn("Tarjeta ($)", min_value=0.0, format="$%d"),
                    },
                    hide_index=True, use_container_width=True, key="editor_auditoria_v5"
                )

                # --- RE-CÁLCULOS SINCRONIZADOS ---
                v_bruta = df_editado["Total_Dinero"].sum()
                v_efectivo_audit = df_editado["Efectivo_R"].sum()
                v_nequi_audit = df_editado["Nequi_R"].sum()
                v_tarjeta_audit = df_editado["Tarjeta_R"].sum()

                # Gastos (Cruce con LOG_PAGOS_GASTOS por fecha exacta)
                df_g["Fecha"] = df_g["Fecha"].astype(str)
                gastos_turno = df_g[(df_g["Fecha"] == str(fecha_turno)) & (df_g["Metodo"].str.contains("Efectivo", case=False, na=False))].copy()
                total_gastos = pd.to_numeric(gastos_turno["Monto"], errors='coerce').fillna(0).sum()

                debe_haber = v_efectivo_audit - total_gastos

                # Dashboard de Auditoría
                st.write("")
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("VENTA BRUTA", formato_moneda(v_bruta))
                k2.metric("EFECTIVO (Auditado)", formato_moneda(v_efectivo_audit))
                k3.metric("GASTOS (Caja)", f"- {formato_moneda(total_gastos)}", delta_color="inverse")
                k4.metric("DEBE HABER", formato_moneda(debe_haber))

                # Alerta de descuadre en la edición
                df_editado["Check"] = df_editado["Efectivo_R"] + df_editado["Nequi_R"] + df_editado["Tarjeta_R"]
                if any(abs(df_editado["Check"] - df_editado["Total_Dinero"]) > 1):
                    st.error("⚠️ La suma de los pagos no coincide con el valor de algunos tickets. Verifica los montos.")

                st.markdown("---")
                
                # --- ARQUEO FÍSICO FINAL ---
                c_real, c_z = st.columns(2)
                f_real = c_real.number_input("💵 Efectivo Físico Recibido (Contado):", min_value=0.0, step=1000.0)
                z_rep = c_z.text_input("📑 Z-Report / Ticket:", value=shift_id_real[:10])

                diff = f_real - debe_haber
                if diff == 0: st.success("### ✅ CAJA CUADRADA")
                elif diff > 0: st.info(f"### 🔵 SOBRANTE: {formato_moneda(diff)}")
                else: st.error(f"### 🔴 FALTANTE: {formato_moneda(diff)}")

                # --- AHORRO (PROFIT FIRST) ---
                st.markdown("#### 🐷 Reserva para Banco Profit")
                pct = st.slider("% Ahorro Sugerido", 1, 15, 5)
                ahorro = v_bruta * (pct / 100)
                st.warning(f"Se registrará un ahorro de **{formato_moneda(ahorro)}** en el Banco Profit.")

                if st.button("🔒 GUARDAR Y FINALIZAR AUDITORÍA", type="primary", use_container_width=True):
                    # Guardar en LOG_CIERRES_CAJA
                    # Columnas: Fecha, Hora, Teórico, Real, Diferencia, Digital, Tarjeta, Notas, Ahorro, Estado, ID_Loyverse
                    datos = [fecha_turno, datetime.now(ZONA_HORARIA).strftime("%H:%M"), 
                             debe_haber, f_real, diff, v_nequi_audit, v_tarjeta_audit, 
                             "Auditoría Detallada", ahorro, "Pendiente", shift_id_real]
                    
                    try:
                        sheet.worksheet(HOJA_CIERRES).append_row(datos)
                        st.balloons(); st.success("Auditado con éxito."); time.sleep(1.5); st.rerun()
                    except Exception as e: st.error(f"Error al guardar: {e}")

    with tab_hist:
        st.subheader("📜 Historial de Turnos Auditados")
        if not df_c.empty:
            df_c_ver = df_c.sort_values("Fecha", ascending=False)
            st.dataframe(df_c_ver[["Fecha", "Saldo_Real_Con", "Diferencia", "Profit_Retenido", "Numero_Cierre_Loyverse"]], 
                         use_container_width=True, hide_index=True)

    with tab_dash:
        st.subheader("📊 Análisis de Diferencias")
        if not df_c.empty:
            df_c["Diferencia"] = pd.to_numeric(df_c["Diferencia"], errors='coerce').fillna(0)
            fig = px.bar(df_c, x="Fecha", y="Diferencia", color="Diferencia", 
                         title="Sobrantes y Faltantes por Fecha", color_continuous_scale="RdBu")
            st.plotly_chart(fig, use_container_width=True)
