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
    st.caption("Sincronización por Turnos con edición de pagos por Ticket.")

    # 1. CARGA DE DATOS
    try:
        df_v = leer_datos_seguro(sheet.worksheet(HOJA_VENTAS))
        df_g = leer_datos_seguro(sheet.worksheet(HOJA_GASTOS))
        df_c = leer_datos_seguro(sheet.worksheet(HOJA_CIERRES))
    except:
        st.error("Error conectando con la base de datos.")
        return

    if df_v.empty:
        st.warning("No hay datos de ventas disponibles.")
        return

    col_id = "Shift_ID"

    tab_audit, tab_hist, tab_dash = st.tabs(["🔎 AUDITAR TURNO", "📜 HISTORIAL", "📊 DASHBOARD"])

    with tab_audit:
        # --- LÓGICA DE FECHAS (IGUAL A VENTAS PARA NO SALTAR DÍAS) ---
        df_v["Fecha_DT"] = pd.to_datetime(df_v["Fecha"], errors='coerce')
        df_v = df_v.sort_values("Fecha_DT", ascending=False)
        
        # Identificar turnos ya auditados
        auditados = []
        if not df_c.empty and "Numero_Cierre_Loyverse" in df_c.columns:
            auditados = df_c["Numero_Cierre_Loyverse"].astype(str).unique().tolist()
        
        df_v[col_id] = df_v[col_id].astype(str).str.strip()
        
        # Filtro de pendientes (IDs válidos y no auditados)
        df_pendientes = df_v[
            (~df_v[col_id].isin(auditados)) & 
            (df_v[col_id] != "nan") & (df_v[col_id] != "")
        ].copy()

        if df_pendientes.empty:
            st.success("✅ Todos los turnos han sido auditados.")
        else:
            # Selector de Mes (Ordenado)
            df_pendientes["Mes_Label"] = df_pendientes["Fecha_DT"].dt.strftime('%m - %Y')
            meses_opciones = df_pendientes.sort_values("Fecha_DT", ascending=False)["Mes_Label"].unique().tolist()
            
            c_mes, c_turno = st.columns([1, 2])
            mes_sel = c_mes.selectbox("Filtrar por Mes:", meses_opciones)
            
            df_mes = df_pendientes[df_pendientes["Mes_Label"] == mes_sel]
            df_v["Total_Dinero"] = pd.to_numeric(df_v["Total_Dinero"], errors='coerce').fillna(0)
            
            # Lista de Turnos
            lista_final_turnos = []
            ids_finales = []
            shifts_unicos = df_mes[col_id].unique().tolist()
            
            for s in shifts_unicos:
                data_s = df_v[df_v[col_id] == s]
                f_str = data_s["Fecha"].iloc[0]
                t_v = data_s["Total_Dinero"].sum()
                lista_final_turnos.append(f"{f_str} | Turno: {s[:6]} | {formato_moneda(t_v)}")
                ids_finales.append(s)

            seleccion_label = c_turno.selectbox("📋 Selecciona el Turno:", lista_final_turnos)
            
            if seleccion_label:
                shift_id_real = ids_finales[lista_final_turnos.index(seleccion_label)]
                df_sel = df_v[df_v[col_id] == shift_id_real].copy()
                fecha_turno = df_sel["Fecha"].iloc[0]

                st.markdown(f"### 🛡️ Auditoría Turno: `{shift_id_real[:15]}...`")

                # --- SECCIÓN: AUDITORÍA DE TICKETS (EDITABLE) ---
                st.markdown("#### 🎫 Auditoría de Tickets (Desglose de Pagos)")
                st.info("💡 Si un ticket se pagó con varios medios, edita las columnas de la derecha.")

                # Preparar datos por ticket
                df_tickets = df_sel.groupby("Numero_Recibo").agg({
                    "Total_Dinero": "sum",
                    "Metodo_Pago_Real_Auditado": "first"
                }).reset_index()

                # Añadir columnas para edición manual de montos
                # Inicializamos: si el sistema dice 'Efectivo', ponemos el total en 'Efectivo_Real'
                df_tickets["Efectivo_Real"] = df_tickets.apply(lambda x: x["Total_Dinero"] if x["Metodo_Pago_Real_Auditado"] == "Efectivo" else 0.0, axis=1)
                df_tickets["Nequi_Real"] = df_tickets.apply(lambda x: x["Total_Dinero"] if x["Metodo_Pago_Real_Auditado"] == "Nequi" else 0.0, axis=1)
                df_tickets["Tarjeta_Real"] = df_tickets.apply(lambda x: x["Total_Dinero"] if x["Metodo_Pago_Real_Auditado"] == "Tarjeta" else 0.0, axis=1)

                # Editor de Datos
                df_editado = st.data_editor(
                    df_tickets[["Numero_Recibo", "Total_Dinero", "Metodo_Pago_Real_Auditado", "Efectivo_Real", "Nequi_Real", "Tarjeta_Real"]],
                    column_config={
                        "Numero_Recibo": st.column_config.TextColumn("Ticket #", disabled=True),
                        "Total_Dinero": st.column_config.NumberColumn("Valor Total", format="$%d", disabled=True),
                        "Metodo_Pago_Real_Auditado": st.column_config.TextColumn("Ventas Marcó", disabled=True),
                        "Efectivo_Real": st.column_config.NumberColumn("Efectivo ($)", min_value=0.0, format="$%d"),
                        "Nequi_Real": st.column_config.NumberColumn("Nequi ($)", min_value=0.0, format="$%d"),
                        "Tarjeta_Real": st.column_config.NumberColumn("Tarjeta ($)", min_value=0.0, format="$%d"),
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="editor_tickets_split"
                )

                # --- RE-CÁLCULO BASADO EN LA EDICIÓN ---
                v_bruta = df_editado["Total_Dinero"].sum()
                v_efectivo_audit = df_editado["Efectivo_Real"].sum()
                v_nequi_audit = df_editado["Nequi_Real"].sum()
                v_tarjeta_audit = df_editado["Tarjeta_Real"].sum()

                # Gastos (Relación automática)
                df_g["Fecha"] = df_g["Fecha"].astype(str)
                gastos_dia = df_g[(df_g["Fecha"] == str(fecha_turno)) & (df_g["Metodo"].str.contains("Efectivo", case=False, na=False))].copy()
                total_gastos = pd.to_numeric(gastos_dia["Monto"], errors='coerce').fillna(0).sum()

                debe_haber = v_efectivo_audit - total_gastos

                # Cuadros de mando actualizados dinámicamente
                st.write("")
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Venta Bruta", formato_moneda(v_bruta))
                k2.metric("Efectivo (Auditado)", formato_moneda(v_efectivo_audit))
                k3.metric("Gastos Caja", f"- {formato_moneda(total_gastos)}", delta_color="inverse")
                k4.metric("DEBE HABER", formato_moneda(debe_haber))

                # Alerta si el usuario no ha cuadrado los montos de los tickets
                df_editado["Suma_Manual"] = df_editado["Efectivo_Real"] + df_editado["Nequi_Real"] + df_editado["Tarjeta_Real"]
                descuadres = df_editado[abs(df_editado["Suma_Manual"] - df_editado["Total_Dinero"]) > 1]
                if not descuadres.empty:
                    st.error(f"⚠️ Atención: Hay {len(descuadres)} tickets donde la suma de pagos no coincide con el valor del ticket.")

                st.markdown("---")
                
                # --- VALIDACIÓN FÍSICA ---
                cc1, cc2 = st.columns(2)
                efectivo_fisico = cc1.number_input("💵 Efectivo Físico Contado:", min_value=0.0, step=500.0)
                z_report = cc2.text_input("📑 Z-Report / Ticket:", value=shift_id_real[:10])

                diferencia = efectivo_fisico - debe_haber
                if diferencia == 0: st.success("### ✅ CAJA CUADRADA")
                elif diferencia > 0: st.info(f"### 🔵 SOBRANTE: {formato_moneda(diferencia)}")
                else: st.error(f"### 🔴 FALTANTE: {formato_moneda(diferencia)}")

                st.markdown("#### 🐷 Reserva para Banco Profit")
                pct = st.slider("% Ahorro Sugerido", 1, 15, 5)
                ahorro = v_bruta * (pct / 100)
                st.warning(f"Se registrará un ahorro de **{formato_moneda(ahorro)}**")

                if st.button("🔒 GUARDAR AUDITORÍA FINAL", type="primary", use_container_width=True):
                    if not descuadres.empty:
                        st.warning("No puedes guardar si los montos de los tickets no coinciden con su valor total.")
                    else:
                        datos = [fecha_turno, datetime.now(ZONA_HORARIA).strftime("%H:%M"), 
                                 debe_haber, efectivo_fisico, diferencia, 
                                 v_nequi_audit, v_tarjeta_audit, "Auditado por tickets", ahorro, "Pendiente", shift_id_real]
                        try:
                            sheet.worksheet(HOJA_CIERRES).append_row(datos)
                            st.balloons(); st.success("Auditado con éxito."); time.sleep(2); st.rerun()
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
