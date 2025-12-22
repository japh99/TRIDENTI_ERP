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
    st.title("🔐 Tesorería: Auditoría Maestra")
    st.caption("Sincronización basada en Shift_ID (Loyverse).")

    # 1. CARGA DE DATOS
    try:
        df_v = leer_datos_seguro(sheet.worksheet(HOJA_VENTAS))
        df_g = leer_datos_seguro(sheet.worksheet(HOJA_GASTOS))
        df_c = leer_datos_seguro(sheet.worksheet(HOJA_CIERRES))
    except:
        st.error("Error conectando con la base de datos.")
        return

    if df_v.empty:
        st.warning("No hay ventas registradas.")
        return

    col_id = "Shift_ID"
    tab_audit, tab_hist, tab_dash = st.tabs(["🔎 AUDITAR TURNO", "📜 HISTORIAL", "📊 DASHBOARD"])

    with tab_audit:
        # --- PROCESAMIENTO DE TURNOS (LÓGICA ACTUAL PRESERVADA) ---
        df_v[col_id] = df_v[col_id].astype(str).str.strip()
        df_v["Total_Dinero"] = pd.to_numeric(df_v["Total_Dinero"], errors='coerce').fillna(0)
        
        auditados = []
        if not df_c.empty and "Numero_Cierre_Loyverse" in df_c.columns:
            auditados = df_c["Numero_Cierre_Loyverse"].astype(str).str.strip().unique().tolist()

        resumen_shifts = df_v.groupby(col_id).agg({
            "Fecha": ["min", "max"],
            "Total_Dinero": "sum"
        }).reset_index()
        resumen_shifts.columns = [col_id, "Fecha_Inicio", "Fecha_Fin", "Venta_Total"]

        df_pendientes = resumen_shifts[~resumen_shifts[col_id].isin(auditados)].copy()
        df_pendientes = df_pendientes[df_pendientes[col_id] != "nan"]

        if df_pendientes.empty:
            st.success("🎉 Todos los turnos han sido auditados.")
        else:
            df_pendientes["Fecha_Ini_DT"] = pd.to_datetime(df_pendientes["Fecha_Inicio"], errors='coerce')
            df_pendientes = df_pendientes.sort_values("Fecha_Ini_DT", ascending=False)
            df_pendientes["Mes_Label"] = df_pendientes["Fecha_Ini_DT"].dt.strftime('%m - %Y')
            meses_disp = sorted(df_pendientes["Mes_Label"].unique().tolist(), reverse=True)
            
            c_mes, c_turno = st.columns([1, 2])
            mes_sel = c_mes.selectbox("Filtrar Mes:", meses_disp)
            df_mes = df_pendientes[df_pendientes["Mes_Label"] == mes_sel]

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

                # --- EDITOR DE TICKETS ---
                st.markdown("#### 🎫 Desglose de Pagos por Ticket")
                col_aud = "Metodo_Pago_Real_Auditado"
                df_tickets = df_sel.groupby("Numero_Recibo").agg({
                    "Total_Dinero": "sum",
                    col_aud: "first"
                }).reset_index()

                df_tickets["Efectivo_Real"] = df_tickets.apply(lambda x: x["Total_Dinero"] if x[col_aud] == "Efectivo" else 0.0, axis=1)
                df_tickets["Nequi_Real"] = df_tickets.apply(lambda x: x["Total_Dinero"] if x[col_aud] == "Nequi" else 0.0, axis=1)
                df_tickets["Tarjeta_Real"] = df_tickets.apply(lambda x: x["Total_Dinero"] if x[col_aud] == "Tarjeta" else 0.0, axis=1)

                df_editado = st.data_editor(
                    df_tickets[["Numero_Recibo", "Total_Dinero", "Efectivo_Real", "Nequi_Real", "Tarjeta_Real"]],
                    column_config={
                        "Numero_Recibo": st.column_config.TextColumn("Ticket #", disabled=True),
                        "Total_Dinero": st.column_config.NumberColumn("Valor Ticket", format="$%d", disabled=True),
                        "Efectivo_Real": st.column_config.NumberColumn("Efectivo ($)", min_value=0.0, format="$%d"),
                        "Nequi_Real": st.column_config.NumberColumn("Nequi ($)", min_value=0.0, format="$%d"),
                        "Tarjeta_Real": st.column_config.NumberColumn("Tarjeta ($)", min_value=0.0, format="$%d"),
                    },
                    hide_index=True, use_container_width=True, key="editor_split_v8"
                )

                # --- RE-CÁLCULOS ---
                v_bruta = df_editado["Total_Dinero"].sum()
                v_efec_total = df_editado["Efectivo_Real"].sum()
                v_nequi_total = df_editado["Nequi_Real"].sum()
                v_tarjeta_total = df_editado["Tarjeta_Real"].sum()

                # --- SINCRONIZACIÓN DE GASTOS (EL ARREGLO) ---
                # Convertimos las fechas de ambos lados a formato YYYY-MM-DD para que coincidan 100%
                fechas_turno_norm = pd.to_datetime(df_sel["Fecha"]).dt.strftime('%Y-%m-%d').unique().tolist()
                df_g["Fecha_Norm"] = pd.to_datetime(df_g["Fecha"], errors='coerce').dt.strftime('%Y-%m-%d')
                
                # Buscamos por la columna 'Metodo' o 'Medio de Pago' (buscamos la que exista)
                col_metodo_g = "Metodo" if "Metodo" in df_g.columns else "Medio de Pago"
                
                if col_metodo_g in df_g.columns:
                    gastos_turno = df_g[
                        (df_g["Fecha_Norm"].isin(fechas_turno_norm)) & 
                        (df_g[col_metodo_g].str.contains("Efectivo", case=False, na=False))
                    ].copy()
                else:
                    gastos_turno = pd.DataFrame()

                total_gastos = pd.to_numeric(gastos_turno["Monto"], errors='coerce').fillna(0).sum()
                debe_haber = v_efec_total - total_gastos

                # DASHBOARD
                st.write("")
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("VENTA BRUTA", formato_moneda(v_bruta))
                k2.metric("EFECTIVO (Auditado)", formato_moneda(v_efec_total))
                k3.metric("GASTOS EN CAJA", f"- {formato_moneda(total_gastos)}", delta_color="inverse")
                k4.metric("DEBE HABER", formato_moneda(debe_haber))

                if not gastos_turno.empty:
                    with st.expander("📍 Ver gastos detectados en este turno"):
                        st.table(gastos_turno[["Fecha", "Concepto", "Monto", "Responsable"]])

                st.markdown("---")
                c_real, c_z = st.columns(2)
                f_real = c_real.number_input("💵 Efectivo Físico Recibido:", min_value=0.0, step=1000.0)
                z_rep = c_z.text_input("📑 Z-Report / Ticket:", value=shift_id_real[:10])

                diff = f_real - debe_haber
                if diff == 0: st.success("### ✅ CAJA CUADRADA")
                elif diff > 0: st.info(f"### 🔵 SOBRANTE: {formato_moneda(diff)}")
                else: st.error(f"### 🔴 FALTANTE: {formato_moneda(diff)}")

                st.markdown("#### 🐷 Reserva para Banco Profit")
                pct = st.slider("% Ahorro Sugerido", 1, 15, 5)
                ahorro = v_bruta * (pct / 100)
                st.warning(f"Reserva: **{formato_moneda(ahorro)}**")

                if st.button("🔒 GUARDAR AUDITORÍA FINAL", type="primary", use_container_width=True):
                    df_editado["Check"] = df_editado["Efectivo_Real"] + df_editado["Nequi_Real"] + df_editado["Tarjeta_Real"]
                    if any(abs(df_editado["Check"] - df_editado["Total_Dinero"]) > 1):
                        st.error("La suma de pagos no coincide con el valor total.")
                    else:
                        fecha_ref = df_sel["Fecha"].max()
                        datos = [fecha_ref, datetime.now(ZONA_HORARIA).strftime("%H:%M"), debe_haber, f_real, diff, v_nequi_total, v_tarjeta_total, "Auditoría Split", ahorro, "Pendiente", shift_id_real]
                        try:
                            sheet.worksheet(HOJA_CIERRES).append_row(datos)
                            st.balloons(); st.success("Guardado."); time.sleep(1.5); st.rerun()
                        except Exception as e: st.error(f"Error: {e}")

    with tab_hist:
        st.subheader("📜 Historial de Turnos Auditados")
        if not df_c.empty:
            st.dataframe(df_c.sort_values("Fecha", ascending=False), use_container_width=True, hide_index=True)

    with tab_dash:
        st.subheader("📊 Dashboard")
        if not df_c.empty:
            df_c["Diferencia"] = pd.to_numeric(df_c["Diferencia"], errors='coerce').fillna(0)
            st.plotly_chart(px.bar(df_c, x="Fecha", y="Diferencia", color="Diferencia", title="Diferencias de Caja"), use_container_width=True)
