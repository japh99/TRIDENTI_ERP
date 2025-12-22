import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import time
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero

# --- CONFIGURACIÓN DE HOJAS ---
HOJA_VENTAS = "LOG_VENTAS_LOYVERSE"
HOJA_GASTOS = "LOG_PAGOS_GASTOS"
HOJA_CIERRES = "LOG_CIERRES_CAJA"

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

def show(sheet):
    st.title("🔐 Tesorería: Auditoría Maestra de Cierres")
    st.caption("Sincronización total con Ventas y Gastos. Auditoría por Turnos Reales (Shifts).")

    # 1. CARGA DE DATOS
    try:
        df_v = leer_datos_seguro(sheet.worksheet(HOJA_VENTAS))
        df_g = leer_datos_seguro(sheet.worksheet(HOJA_GASTOS))
        df_c = leer_datos_seguro(sheet.worksheet(HOJA_CIERRES))
    except:
        st.error("Error conectando con la base de datos.")
        return

    if df_v.empty:
        st.warning("No hay ventas registradas. Escanea cierres en Ventas primero.")
        return

    col_id = "Shift_ID"

    tab_audit, tab_hist, tab_dash = st.tabs(["🔎 AUDITAR TURNO", "📜 HISTORIAL", "📊 DASHBOARD"])

    with tab_audit:
        # --- PROCESAMIENTO DE DATOS ---
        df_v[col_id] = df_v[col_id].astype(str).str.strip()
        df_v["Total_Dinero"] = pd.to_numeric(df_v["Total_Dinero"], errors='coerce').fillna(0)
        
        # Identificar qué turnos ya fueron auditados
        auditados = []
        if not df_c.empty and "Numero_Cierre_Loyverse" in df_c.columns:
            auditados = df_c["Numero_Cierre_Loyverse"].astype(str).str.strip().unique().tolist()

        # AGRUPAR POR TURNO PARA IDENTIFICAR EL RANGO DE FECHAS (Solución día 20)
        resumen_shifts = df_v.groupby(col_id).agg({
            "Fecha": ["min", "max"],
            "Total_Dinero": "sum"
        }).reset_index()
        resumen_shifts.columns = [col_id, "Fecha_Inicio", "Fecha_Fin", "Venta_Total"]

        # Filtrar pendientes
        df_pendientes = resumen_shifts[
            (~resumen_shifts[col_id].isin(auditados)) & 
            (resumen_shifts[col_id] != "nan")
        ].copy()

        if df_pendientes.empty:
            st.success("🎉 ¡Todos los turnos están auditados y al día!")
        else:
            # ORGANIZACIÓN POR MESES
            df_pendientes["Fecha_Fin_DT"] = pd.to_datetime(df_pendientes["Fecha_Fin"], errors='coerce')
            df_pendientes = df_pendientes.sort_values("Fecha_Fin_DT", ascending=False)
            
            df_pendientes["Mes_Label"] = df_pendientes["Fecha_Fin_DT"].dt.strftime('%m - %Y')
            meses_disp = sorted(df_pendientes["Mes_Label"].unique().tolist(), reverse=True)
            
            c_mes, c_turno = st.columns([1, 2])
            mes_sel = c_mes.selectbox("Filtrar Mes:", meses_disp)
            
            df_mes = df_pendientes[df_pendientes["Mes_Label"] == mes_sel]

            # Crear etiquetas para el selector
            lista_opciones = []
            for _, row in df_mes.iterrows():
                f_ini, f_fin = row["Fecha_Inicio"], row["Fecha_Fin"]
                rango = f_ini if f_ini == f_fin else f"{f_ini} al {f_fin}"
                label = f"📅 {rango} | Total: {formato_moneda(row['Venta_Total'])} | ID: {row[col_id][:6]}"
                lista_opciones.append(label)

            seleccion = c_turno.selectbox("📋 Selecciona el Turno a auditar:", lista_opciones)
            
            if seleccion:
                shift_id_real = df_mes.iloc[lista_opciones.index(seleccion)][col_id]
                df_sel = df_v[df_v[col_id] == shift_id_real].copy()
                
                st.markdown(f"### 🛡️ Auditoría del Turno: `{shift_id_real}`")

                # --- EDITOR DE TICKETS (EDICIÓN DE VALORES REALES) ---
                st.markdown("#### 🎫 Desglose de Pagos por Ticket")
                st.info("💡 Haz doble clic para repartir el dinero si el cliente pagó con varios métodos.")

                # Nombre de la columna que viene auditada de Ventas
                col_aud_ventas = "Metodo_Pago_Real_Auditado" if "Metodo_Pago_Real_Auditado" in df_sel.columns else "Metodo_Pago_Loyverse"

                df_tickets = df_sel.groupby("Numero_Recibo").agg({
                    "Total_Dinero": "sum",
                    col_aud_ventas: "first"
                }).reset_index()

                # Preparar columnas para edición manual
                df_tickets["Efectivo_R"] = df_tickets.apply(lambda x: x["Total_Dinero"] if x[col_aud_ventas] == "Efectivo" else 0.0, axis=1)
                df_tickets["Nequi_R"] = df_tickets.apply(lambda x: x["Total_Dinero"] if x[col_aud_ventas] == "Nequi" else 0.0, axis=1)
                df_tickets["Tarjeta_R"] = df_tickets.apply(lambda x: x["Total_Dinero"] if x[col_aud_ventas] == "Tarjeta" else 0.0, axis=1)

                df_editado = st.data_editor(
                    df_tickets[["Numero_Recibo", "Total_Dinero", "Efectivo_R", "Nequi_R", "Tarjeta_R"]],
                    column_config={
                        "Numero_Recibo": st.column_config.TextColumn("Ticket #", disabled=True),
                        "Total_Dinero": st.column_config.NumberColumn("Valor Ticket", format="$%d", disabled=True),
                        "Efectivo_R": st.column_config.NumberColumn("Efectivo ($)", min_value=0.0, format="$%d"),
                        "Nequi_R": st.column_config.NumberColumn("Nequi ($)", min_value=0.0, format="$%d"),
                        "Tarjeta_R": st.column_config.NumberColumn("Tarjeta ($)", min_value=0.0, format="$%d"),
                    },
                    hide_index=True, use_container_width=True, key="editor_teso_v7"
                )

                # --- RE-CÁLCULOS ---
                v_bruta = df_editado["Total_Dinero"].sum()
                v_efec_audit = df_editado["Efectivo_R"].sum()
                v_nequi_audit = df_editado["Nequi_R"].sum()
                v_tarjeta_audit = df_editado["Tarjeta_R"].sum()

                # --- CRUCE CON GASTOS (MULTI-FECHA) ---
                # Buscamos gastos de TODAS las fechas que abarcó este turno
                fechas_del_turno = df_sel["Fecha"].unique().tolist()
                df_g["Fecha_Str"] = df_g["Fecha"].astype(str)
                
                gastos_turno = df_g[
                    (df_g["Fecha_Str"].isin(fechas_del_turno)) & 
                    (df_g["Metodo"].str.contains("Efectivo", case=False, na=False))
                ].copy()
                
                total_gastos = pd.to_numeric(gastos_turno["Monto"], errors='coerce').fillna(0).sum()
                debe_haber = v_efec_audit - total_gastos

                # DASHBOARD DE AUDITORÍA (Estilo Card Dorado)
                st.write("")
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("VENTA BRUTA", formato_moneda(v_bruta))
                k2.metric("EFECTIVO (Auditado)", formato_moneda(v_efec_audit))
                k3.metric("GASTOS (Caja)", f"- {formato_moneda(total_gastos)}", delta_color="inverse")
                k4.metric("DEBE HABER", formato_moneda(debe_haber))

                if not gastos_turno.empty:
                    with st.expander("📍 Ver gastos detectados en este turno"):
                        st.table(gastos_turno[["Fecha", "Concepto", "Monto", "Responsable"]])

                # Validación de suma de tickets
                df_editado["Check"] = df_editado["Efectivo_R"] + df_editado["Nequi_R"] + df_editado["Tarjeta_R"]
                if any(abs(df_editado["Check"] - df_editado["Total_Dinero"]) > 1):
                    st.error("⚠️ La suma de los pagos no coincide con el valor total en algunos tickets.")

                st.markdown("---")
                
                # --- VALIDACIÓN FINAL ---
                c_real, c_z = st.columns(2)
                f_real = c_real.number_input("💵 Efectivo Físico Recibido (Contado):", min_value=0.0, step=1000.0)
                z_rep = c_z.text_input("📑 Z-Report / Ticket Loyverse:", value=shift_id_real[:10])

                diff = f_real - debe_haber
                if diff == 0: st.success("### ✅ CAJA CUADRADA")
                elif diff > 0: st.info(f"### 🔵 SOBRANTE: {formato_moneda(diff)}")
                else: st.error(f"### 🔴 FALTANTE: {formato_moneda(diff)}")

                # AHORRO
                st.markdown("#### 🐷 Reserva para Banco Profit")
                pct = st.slider("% Ahorro Sugerido (Sobre Venta Bruta)", 1, 15, 5)
                ahorro = v_bruta * (pct / 100)
                st.warning(f"Se generará una reserva de **{formato_moneda(ahorro)}**")

                if st.button("🔒 GUARDAR AUDITORÍA FINAL", type="primary", use_container_width=True):
                    # Usamos la fecha final del turno para el registro
                    fecha_ref = df_sel["Fecha"].max()
                    # Columnas LOG_CIERRES_CAJA: Fecha, Hora, Teórico, Real, Diferencia, Digital, Tarjeta, Notas, Ahorro, Estado, ID_Loyverse
                    datos = [fecha_ref, datetime.now(ZONA_HORARIA).strftime("%H:%M"), 
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
        st.subheader("📊 Dashboard")
        if not df_c.empty:
            df_c["Diferencia"] = pd.to_numeric(df_c["Diferencia"], errors='coerce').fillna(0)
            st.plotly_chart(px.bar(df_c, x="Fecha", y="Diferencia", color="Diferencia", title="Balance de Diferencias por Fecha"), use_container_width=True)
