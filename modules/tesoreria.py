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
    st.caption("Sincronización total con los turnos descargados de Loyverse.")

    # 1. CARGA DE DATOS
    try:
        df_v = leer_datos_seguro(sheet.worksheet(HOJA_VENTAS))
        df_g = leer_datos_seguro(sheet.worksheet(HOJA_GASTOS))
        df_c = leer_datos_seguro(sheet.worksheet(HOJA_CIERRES))
    except:
        st.error("Error conectando con la base de datos.")
        return

    if df_v.empty:
        st.warning("No hay datos de ventas en la base de datos. Escanea cierres en el módulo de Ventas primero.")
        return

    col_id = "Shift_ID"

    tab_audit, tab_hist, tab_dash = st.tabs(["🔎 AUDITAR TURNO", "📜 HISTORIAL", "📊 DASHBOARD"])

    with tab_audit:
        # --- LÓGICA DE DETECCIÓN DE TURNOS (SINCRONIZADA CON VENTAS) ---
        # Convertimos fechas y ordenamos exactamente igual que en el escaneo de Ventas
        df_v["Fecha_DT"] = pd.to_datetime(df_v["Fecha"], errors='coerce')
        df_v = df_v.sort_values(["Fecha_DT", "Hora"], ascending=[False, False])
        
        # Lista de turnos ya auditados para no repetirlos
        auditados = []
        if not df_c.empty and "Numero_Cierre_Loyverse" in df_c.columns:
            auditados = df_c["Numero_Cierre_Loyverse"].astype(str).unique().tolist()
        
        # Obtenemos los turnos únicos (Shifts)
        df_v[col_id] = df_v[col_id].astype(str).str.strip()
        df_turnos = df_v[df_v[col_id] != "nan"].copy()
        
        # Filtramos los que faltan por auditar
        df_pendientes = df_turnos[~df_turnos[col_id].isin(auditados)].copy()

        if df_pendientes.empty:
            st.success("🎉 ¡Todos los turnos descargados están auditados!")
        else:
            # Selector de Mes para organizar la lista
            df_pendientes["Mes_Label"] = df_pendientes["Fecha_DT"].dt.strftime('%m - %Y')
            meses = df_pendientes["Mes_Label"].unique().tolist()
            
            c_mes, c_turno = st.columns([1, 2])
            mes_sel = c_mes.selectbox("Filtrar Mes:", meses)
            
            # Preparar lista amigable de turnos para el selectbox
            df_mes = df_pendientes[df_pendientes["Mes_Label"] == mes_sel]
            df_v["Total_Dinero"] = pd.to_numeric(df_v["Total_Dinero"], errors='coerce').fillna(0)
            
            opciones_turnos = []
            ids_mapeo = []
            
            for s in df_mes[col_id].unique():
                data_s = df_v[df_v[col_id] == s]
                f_s = data_s["Fecha"].iloc[0]
                t_s = data_s["Total_Dinero"].sum()
                opciones_turnos.append(f"{f_s} | Venta: {formato_moneda(t_s)} | ID: {s[:6]}")
                ids_mapeo.append(s)

            seleccion = c_turno.selectbox("📋 Selecciona el Cierre a auditar:", opciones_turnos)
            
            if seleccion:
                shift_id_real = ids_mapeo[opciones_turnos.index(seleccion)]
                df_sel = df_v[df_v[col_id] == shift_id_real].copy()
                fecha_turno = df_sel["Fecha"].iloc[0]

                st.markdown(f"### 🛡️ Auditando Turno: `{shift_id_real}`")

                # --- EDITOR DE TICKETS (LA SOLUCIÓN AL SPLIT) ---
                st.markdown("#### 🎫 Desglose de Pagos por Ticket")
                st.info("Escribe los valores reales recibidos en cada columna si el cliente pagó con varios medios.")

                # Agrupamos por ticket para el editor
                df_tickets = df_sel.groupby("Numero_Recibo").agg({
                    "Total_Dinero": "sum",
                    "Metodo_Pago_Real_Auditado": "first"
                }).reset_index()

                # Inicializamos las columnas de edición con 0
                df_tickets["Efectivo_R"] = df_tickets.apply(lambda x: x["Total_Dinero"] if x["Metodo_Pago_Real_Auditado"] == "Efectivo" else 0.0, axis=1)
                df_tickets["Nequi_R"] = df_tickets.apply(lambda x: x["Total_Dinero"] if x["Metodo_Pago_Real_Auditado"] == "Nequi" else 0.0, axis=1)
                df_tickets["Tarjeta_R"] = df_tickets.apply(lambda x: x["Total_Dinero"] if x["Metodo_Pago_Real_Auditado"] == "Tarjeta" else 0.0, axis=1)

                df_editado = st.data_editor(
                    df_tickets[["Numero_Recibo", "Total_Dinero", "Efectivo_R", "Nequi_R", "Tarjeta_R"]],
                    column_config={
                        "Numero_Recibo": st.column_config.TextColumn("Ticket #", disabled=True),
                        "Total_Dinero": st.column_config.NumberColumn("Valor Ticket", format="$%d", disabled=True),
                        "Efectivo_R": st.column_config.NumberColumn("Efectivo", min_value=0.0, format="$%d"),
                        "Nequi_R": st.column_config.NumberColumn("Nequi", min_value=0.0, format="$%d"),
                        "Tarjeta_R": st.column_config.NumberColumn("Tarjeta", min_value=0.0, format="$%d"),
                    },
                    hide_index=True, use_container_width=True, key="editor_split_payments"
                )

                # --- RE-CÁLCULOS EN TIEMPO REAL ---
                v_bruta = df_editado["Total_Dinero"].sum()
                v_efectivo_total = df_editado["Efectivo_R"].sum()
                v_nequi_total = df_editado["Nequi_R"].sum()
                v_tarjeta_total = df_editado["Tarjeta_R"].sum()

                # Gastos de Caja (Sincronizados por fecha)
                df_g["Fecha"] = df_g["Fecha"].astype(str)
                gastos_turno = df_g[(df_g["Fecha"] == str(fecha_turno)) & (df_g["Metodo"].str.contains("Efectivo", case=False, na=False))].copy()
                total_gastos = pd.to_numeric(gastos_turno["Monto"], errors='coerce').fillna(0).sum()

                debe_haber = v_efectivo_total - total_gastos

                # Dashboard de Auditoría
                st.write("")
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("VENTA BRUTA", formato_moneda(v_bruta))
                k2.metric("EFECTIVO (Auditado)", formato_moneda(v_efectivo_total))
                k3.metric("GASTOS (Salida)", f"- {formato_moneda(total_gastos)}", delta_color="inverse")
                k4.metric("DEBE HABER", formato_moneda(debe_haber))

                # Validación de suma de tickets
                df_editado["Check"] = df_editado["Efectivo_R"] + df_editado["Nequi_R"] + df_editado["Tarjeta_R"]
                if any(abs(df_editado["Check"] - df_editado["Total_Dinero"]) > 1):
                    st.error("⚠️ La suma de los pagos en algunos tickets no coincide con el valor total del ticket.")

                st.markdown("---")
                
                # ENTRADA DE CAJA REAL
                c_real, c_z = st.columns(2)
                f_real = c_real.number_input("💵 Efectivo Físico Contado:", min_value=0.0, step=1000.0)
                z_rep = c_z.text_input("📑 Z-Report / Ticket:", value=shift_id_real[:10])

                diff = f_real - debe_haber
                if diff == 0: st.success("### ✅ CAJA CUADRADA")
                elif diff > 0: st.info(f"### 🔵 SOBRANTE: {formato_moneda(diff)}")
                else: st.error(f"### 🔴 FALTANTE: {formato_moneda(diff)}")

                # AHORRO
                st.markdown("#### 🐷 Reserva Banco Profit")
                pct = st.slider("% Ahorro (Sobre Venta Bruta)", 1, 15, 5)
                monto_ahorro = v_bruta * (pct / 100)
                st.warning(f"Se enviará orden de ahorro por: **{formato_moneda(monto_ahorro)}**")

                if st.button("🔒 GUARDAR Y FINALIZAR AUDITORÍA", type="primary", use_container_width=True):
                    # Datos para LOG_CIERRES_CAJA
                    # Columnas: Fecha, Hora, Teórico, Real, Dif, Digital, Tarjeta, Notas, Ahorro, Estado, ID_Loyverse
                    datos = [fecha_turno, datetime.now(ZONA_HORARIA).strftime("%H:%M"), 
                             debe_haber, f_real, diff, v_nequi_total, v_tarjeta_total, 
                             "Auditoría Split", monto_ahorro, "Pendiente", shift_id_real]
                    
                    try:
                        sheet.worksheet(HOJA_CIERRES).append_row(datos)
                        st.balloons(); st.success("Guardado."); time.sleep(1.5); st.rerun()
                    except Exception as e: st.error(f"Error: {e}")

    with tab_hist:
        st.subheader("📜 Historial de Turnos")
        if not df_c.empty:
            st.dataframe(df_c.sort_values("Fecha", ascending=False), use_container_width=True, hide_index=True)

    with tab_dash:
        st.subheader("📊 Dashboard")
        if not df_c.empty:
            df_c["Diferencia"] = pd.to_numeric(df_c["Diferencia"], errors='coerce').fillna(0)
            st.plotly_chart(px.bar(df_c, x="Fecha", y="Diferencia", color="Diferencia", title="Sobrantes/Faltantes"), use_container_width=True)
