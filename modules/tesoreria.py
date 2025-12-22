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
    st.title("🔐 Tesorería: Auditoría de Turnos Reales")
    st.caption("Sincronización basada en Shift_ID (Loyverse). Agrupa turnos que cruzan la medianoche.")

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
        # --- PROCESAMIENTO DE TURNOS REALES (SHIFTS) ---
        df_v[col_id] = df_v[col_id].astype(str).str.strip()
        df_v["Total_Dinero"] = pd.to_numeric(df_v["Total_Dinero"], errors='coerce').fillna(0)
        
        # Identificar qué IDs de turno ya existen en la hoja de Tesorería
        auditados = []
        if not df_c.empty and "Numero_Cierre_Loyverse" in df_c.columns:
            auditados = df_c["Numero_Cierre_Loyverse"].astype(str).str.strip().unique().tolist()

        # AGRUPAR VENTAS POR TURNO (SHIFT)
        # Aquí calculamos qué fechas abarca cada turno y el total de dinero
        resumen_shifts = df_v.groupby(col_id).agg({
            "Fecha": ["min", "max"],
            "Total_Dinero": "sum"
        }).reset_index()
        resumen_shifts.columns = [col_id, "Fecha_Inicio", "Fecha_Fin", "Venta_Total"]

        # Filtrar solo los turnos que faltan por auditar
        df_pendientes = resumen_shifts[~resumen_shifts[col_id].isin(auditados)].copy()
        df_pendientes = df_pendientes[df_pendientes[col_id] != "nan"]

        if df_pendientes.empty:
            st.success("🎉 ¡Todos los turnos están auditados y al día!")
        else:
            # --- ORGANIZAR POR MES (USANDO LA FECHA DE INICIO DEL TURNO) ---
            df_pendientes["Fecha_Ini_DT"] = pd.to_datetime(df_pendientes["Fecha_Inicio"], errors='coerce')
            df_pendientes = df_pendientes.sort_values("Fecha_Ini_DT", ascending=False)
            
            df_pendientes["Mes_Label"] = df_pendientes["Fecha_Ini_DT"].dt.strftime('%m - %Y')
            meses_disponibles = sorted(df_pendientes["Mes_Label"].unique().tolist(), reverse=True)
            
            c_mes, c_turno = st.columns([1, 2])
            mes_sel = c_mes.selectbox("Filtrar Mes:", meses_disponibles)
            
            df_mes = df_pendientes[df_pendientes["Mes_Label"] == mes_sel]

            # Crear etiquetas para el selector que muestren el rango de fechas
            lista_opciones = []
            for _, row in df_mes.iterrows():
                f_ini, f_fin = row["Fecha_Inicio"], row["Fecha_Fin"]
                rango = f_ini if f_ini == f_fin else f"{f_ini} al {f_fin}"
                label = f"📅 {rango} | Total: {formato_moneda(row['Venta_Total'])} | ID: {row[col_id][:6]}"
                lista_opciones.append(label)

            seleccion = c_turno.selectbox("📋 Selecciona el Turno a auditar:", lista_opciones)
            
            if seleccion:
                # Recuperar el Shift_ID real
                shift_id_real = df_mes.iloc[lista_opciones.index(seleccion)][col_id]
                df_sel = df_v[df_v[col_id] == shift_id_real].copy()
                
                st.markdown(f"### 🛡️ Auditoría del Turno: `{shift_id_real}`")

                # --- EDITOR DE TICKETS (AUDITORÍA DETALLADA) ---
                st.markdown("#### 🎫 Desglose de Pagos por Ticket")
                st.info("💡 Si un ticket se pagó con varios medios, edita los valores en las columnas correspondientes.")

                # Agrupamos por recibo para el editor
                df_tickets = df_sel.groupby("Numero_Recibo").agg({
                    "Total_Dinero": "sum",
                    "Metodo_Pago_Real_Auditado": "first"
                }).reset_index()

                # Columnas para repartir la plata manualmente
                df_tickets["Efectivo_Real"] = df_tickets.apply(lambda x: x["Total_Dinero"] if x["Metodo_Pago_Real_Auditado"] == "Efectivo" else 0.0, axis=1)
                df_tickets["Nequi_Real"] = df_tickets.apply(lambda x: x["Total_Dinero"] if x["Metodo_Pago_Real_Auditado"] == "Nequi" else 0.0, axis=1)
                df_tickets["Tarjeta_Real"] = df_tickets.apply(lambda x: x["Total_Dinero"] if x["Metodo_Pago_Real_Auditado"] == "Tarjeta" else 0.0, axis=1)

                df_editado = st.data_editor(
                    df_tickets[["Numero_Recibo", "Total_Dinero", "Efectivo_Real", "Nequi_Real", "Tarjeta_Real"]],
                    column_config={
                        "Numero_Recibo": st.column_config.TextColumn("Ticket #", disabled=True),
                        "Total_Dinero": st.column_config.NumberColumn("Valor Ticket", format="$%d", disabled=True),
                        "Efectivo_Real": st.column_config.NumberColumn("Efectivo ($)", min_value=0.0, format="$%d"),
                        "Nequi_Real": st.column_config.NumberColumn("Nequi ($)", min_value=0.0, format="$%d"),
                        "Tarjeta_Real": st.column_config.NumberColumn("Tarjeta ($)", min_value=0.0, format="$%d"),
                    },
                    hide_index=True, use_container_width=True, key="editor_split_v6"
                )

                # --- RE-CÁLCULOS ---
                v_bruta = df_editado["Total_Dinero"].sum()
                v_efectivo_total = df_editado["Efectivo_Real"].sum()
                v_nequi_total = df_editado["Nequi_Real"].sum()
                v_tarjeta_total = df_editado["Tarjeta_Real"].sum()

                # --- RELACIÓN CON GASTOS (TODAS LAS FECHAS DEL TURNO) ---
                fechas_del_turno = df_sel["Fecha"].unique().tolist()
                df_g["Fecha"] = df_g["Fecha"].astype(str)
                gastos_turno = df_g[(df_g["Fecha"].isin(fechas_del_turno)) & (df_g["Metodo"].str.contains("Efectivo", case=False, na=False))].copy()
                total_gastos = pd.to_numeric(gastos_turno["Monto"], errors='coerce').fillna(0).sum()

                debe_haber = v_efectivo_total - total_gastos

                # Dashboard de Auditoría
                st.write("")
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Venta Bruta", formato_moneda(v_bruta))
                k2.metric("Efectivo (Auditado)", formato_moneda(v_efectivo_total))
                k3.metric("Gastos en Caja", f"- {formato_moneda(total_gastos)}", delta_color="inverse")
                k4.metric("DEBE HABER", formato_moneda(debe_haber))

                # Validación de suma
                df_editado["Check"] = df_editado["Efectivo_Real"] + df_editado["Nequi_Real"] + df_editado["Tarjeta_Real"]
                if any(abs(df_editado["Check"] - df_editado["Total_Dinero"]) > 1):
                    st.error("⚠️ La suma de los pagos no coincide con el valor total de los tickets.")

                st.markdown("---")
                
                # --- ARQUEO FÍSICO ---
                cc1, cc2 = st.columns(2)
                f_real = cc1.number_input("💵 Efectivo Físico Recibido (Contado):", min_value=0.0, step=1000.0)
                z_rep = cc2.text_input("📑 Z-Report / Ticket Loyverse:", value=shift_id_real[:10])

                diferencia = f_real - debe_haber
                if diferencia == 0: st.success("### ✅ CAJA CUADRADA")
                elif diferencia > 0: st.info(f"### 🔵 SOBRANTE: {formato_moneda(diferencia)}")
                else: st.error(f"### 🔴 FALTANTE: {formato_moneda(diferencia)}")

                # --- AHORRO ---
                st.markdown("#### 🐷 Reserva para Banco Profit")
                pct = st.slider("% Ahorro Sugerido (Sobre Venta Bruta)", 1, 15, 5)
                ahorro = v_bruta * (pct / 100)
                st.warning(f"Se generará una reserva de **{formato_moneda(ahorro)}**")

                if st.button("🔒 GUARDAR AUDITORÍA FINAL", type="primary", use_container_width=True):
                    # Usamos la fecha máxima del turno como fecha de registro
                    fecha_ref = df_sel["Fecha"].max()
                    datos = [fecha_ref, datetime.now(ZONA_HORARIA).strftime("%H:%M"), 
                             debe_haber, f_real, diferencia, v_nequi_total, v_tarjeta_total, 
                             "Auditoría Split Payments", ahorro, "Pendiente", shift_id_real]
                    try:
                        sheet.worksheet(HOJA_CIERRES).append_row(datos)
                        st.balloons(); st.success("Turno Auditado."); time.sleep(1.5); st.rerun()
                    except Exception as e: st.error(f"Error al guardar: {e}")

    with tab_hist:
        st.subheader("📜 Historial de Turnos")
        if not df_c.empty:
            st.dataframe(df_c.sort_values("Fecha", ascending=False), use_container_width=True, hide_index=True)

    with tab_dash:
        st.subheader("📊 Dashboard")
        if not df_c.empty:
            df_c["Diferencia"] = pd.to_numeric(df_c["Diferencia"], errors='coerce').fillna(0)
            st.plotly_chart(px.bar(df_c, x="Fecha", y="Diferencia", color="Diferencia", title="Sobrantes y Faltantes"), use_container_width=True)
