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
    st.title("🔐 Tesorería: Auditoría por Turnos (Shifts)")
    st.caption("Sincronización basada en Shift_ID de Loyverse organizada por meses.")

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

    col_identificador = "Shift_ID"

    tab_audit, tab_hist, tab_dash = st.tabs(["🔎 AUDITAR TURNO", "📜 HISTORIAL", "📊 DASHBOARD"])

    with tab_audit:
        # --- PROCESAMIENTO DE FECHAS Y ORDEN ---
        df_v["Fecha_DT"] = pd.to_datetime(df_v["Fecha"], errors='coerce')
        df_v = df_v.sort_values("Fecha_DT", ascending=False)
        
        # Identificar turnos pendientes
        auditados = []
        if not df_c.empty and "Numero_Cierre_Loyverse" in df_c.columns:
            auditados = df_c["Numero_Cierre_Loyverse"].astype(str).unique().tolist()
        
        df_v[col_identificador] = df_v[col_identificador].astype(str)
        # Solo turnos que no están en la lista de auditados
        df_pendientes = df_v[~df_v[col_identificador].isin(auditados)].copy()
        df_pendientes = df_pendientes[df_pendientes[col_identificador].str.len() > 5] # Filtro de IDs válidos

        if df_pendientes.empty:
            st.success("✅ ¡Todos los turnos están auditados!")
        else:
            # --- SELECTOR DE MES (IGUAL QUE EN VENTAS) ---
            df_pendientes["Mes_Año"] = df_pendientes["Fecha_DT"].dt.strftime('%m - %Y')
            meses_disponibles = df_pendientes["Mes_Año"].unique().tolist()
            
            c_mes, c_turno = st.columns([1, 2])
            mes_sel = c_mes.selectbox("Filtrar por Mes:", meses_disponibles)
            
            # Filtrar turnos del mes seleccionado
            df_mes = df_pendientes[df_pendientes["Mes_Año"] == mes_sel]
            
            # Preparar lista de turnos para el mes seleccionado
            df_v["Total_Dinero"] = pd.to_numeric(df_v["Total_Dinero"], errors='coerce').fillna(0)
            
            lista_turnos_mes = []
            ids_reales = []
            
            # Obtenemos los Shift_ID únicos de este mes preservando el orden de fecha
            shifts_mes = df_mes[col_identificador].unique()
            
            for s in shifts_mes:
                data_shift = df_v[df_v[col_identificador] == s]
                f_c = data_shift["Fecha"].iloc[0]
                t_c = data_shift["Total_Dinero"].sum()
                lista_turnos_mes.append(f"{f_c} | Turno: {s[:6]} | {formato_moneda(t_c)}")
                ids_reales.append(s)

            seleccion_label = c_turno.selectbox("📋 Selecciona el Cierre a auditar:", lista_turnos_mes)
            
            if seleccion_label:
                idx_sel = lista_turnos_mes.index(seleccion_label)
                shift_id_real = ids_reales[idx_sel]
                
                # --- DATOS DEL SHIFT SELECCIONADO ---
                df_sel = df_v[df_v[col_identificador] == shift_id_real].copy()
                fecha_turno = df_sel["Fecha"].iloc[0]
                
                v_bruta = df_sel["Total_Dinero"].sum()
                v_efectivo = df_sel[df_sel["Metodo_Pago_Real_Auditado"] == "Efectivo"]["Total_Dinero"].sum()
                v_digital = df_sel[df_sel["Metodo_Pago_Real_Auditado"].str.contains("Nequi|Davi|Transf", case=False, na=False)]["Total_Dinero"].sum()
                v_tarjetas = df_sel[df_sel["Metodo_Pago_Real_Auditado"] == "Tarjeta"]["Total_Dinero"].sum()

                # --- GASTOS ---
                df_g["Fecha"] = df_g["Fecha"].astype(str)
                gastos_dia = df_g[(df_g["Fecha"] == str(fecha_turno)) & (df_g["Metodo"].str.contains("Efectivo", case=False, na=False))].copy()
                gastos_dia["Monto"] = pd.to_numeric(gastos_dia["Monto"], errors='coerce').fillna(0)
                total_gastos = gastos_dia["Monto"].sum()

                debe_haber = v_efectivo - total_gastos

                st.markdown(f"### 🛡️ Auditoría Turno: `{shift_id_real}`")
                
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Venta Bruta", formato_moneda(v_bruta))
                k2.metric("Efectivo", formato_moneda(v_efectivo))
                k3.metric("Gastos Caja", f"- {formato_moneda(total_gastos)}", delta_color="inverse")
                k4.metric("DEBE HABER", formato_moneda(debe_haber))

                with st.expander("📦 Detalle de Productos"):
                    st.table(df_sel.groupby("Nombre_Plato")["Total_Dinero"].sum().reset_index().sort_values("Total_Dinero", ascending=False))

                st.markdown("---")
                
                cc1, cc2 = st.columns(2)
                efectivo_fisico = cc1.number_input("💵 Efectivo Contado:", min_value=0.0, step=500.0)
                z_report = cc2.text_input("📑 Ticket/Z-Report:", value=shift_id_real[:10])

                diferencia = efectivo_fisico - debe_haber
                if diferencia == 0: st.success("✅ CAJA CUADRADA")
                elif diferencia > 0: st.info(f"### 🔵 SOBRANTE: {formato_moneda(diferencia)}")
                else: st.error(f"### 🔴 FALTANTE: {formato_moneda(diferencia)}")

                st.markdown("#### 🐷 Reserva Profit")
                pct = st.slider("% Ahorro", 1, 15, 5)
                ahorro = v_bruta * (pct / 100)
                st.warning(f"Ahorro estimado: **{formato_moneda(ahorro)}**")

                notas = st.text_area("Notas:")

                if st.button("🔒 GUARDAR AUDITORÍA", type="primary", use_container_width=True):
                    datos = [fecha_turno, datetime.now(ZONA_HORARIA).strftime("%H:%M"), debe_haber, efectivo_fisico, diferencia, v_digital, v_tarjetas, notas, ahorro, "Pendiente", shift_id_real]
                    try:
                        sheet.worksheet(HOJA_CIERRES).append_row(datos)
                        st.balloons(); st.success("Guardado."); time.sleep(2); st.rerun()
                    except Exception as e: st.error(f"Error: {e}")

    with tab_hist:
        st.subheader("📜 Historial")
        if not df_c.empty:
            # Formatear la tabla de historial para que sea legible
            df_c_ver = df_c.sort_values("Fecha", ascending=False)
            st.dataframe(df_c_ver[["Fecha", "Saldo_Real_Con", "Diferencia", "Profit_Retenido", "Numero_Cierre_Loyverse"]], use_container_width=True, hide_index=True)

    with tab_dash:
        st.subheader("📊 Análisis")
        if not df_c.empty:
            df_c["Diferencia"] = pd.to_numeric(df_c["Diferencia"], errors='coerce').fillna(0)
            fig = px.bar(df_c, x="Fecha", y="Diferencia", color="Diferencia", title="Sobrantes y Faltantes")
            st.plotly_chart(fig, use_container_width=True)
