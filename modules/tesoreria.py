import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import time
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero, generar_id

# --- CONFIGURACIÓN DE HOJAS ---
HOJA_VENTAS = "LOG_VENTAS_LOYVERSE"
HOJA_GASTOS = "LOG_PAGOS_GASTOS"
HOJA_CIERRES = "LOG_CIERRES_CAJA"

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

def show(sheet):
    st.title("🔐 Tesorería: Auditoría Gerencial")
    st.caption("Validación de ventas, control de gastos de caja y reserva de utilidades.")

    # 1. CARGA DE DATOS MAESTROS
    try:
        df_v = leer_datos_seguro(sheet.worksheet(HOJA_VENTAS))
        df_g = leer_datos_seguro(sheet.worksheet(HOJA_GASTOS))
        df_c = leer_datos_seguro(sheet.worksheet(HOJA_CIERRES))
    except:
        st.error("Error conectando con la base de datos.")
        return

    tab_audit, tab_hist, tab_dash = st.tabs(["🔎 AUDITAR CIERRE DE VENTAS", "📜 HISTORIAL DE CIERRES", "📊 DASHBOARD"])

    with tab_audit:
        # --- PASO A: IDENTIFICAR CIERRES DE VENTAS DISPONIBLES ---
        df_v["Fecha"] = df_v["Fecha"].astype(str)
        
        # Obtenemos las fechas que tienen ventas pero que NO están en la hoja de cierres (Tesorería)
        fechas_con_venta = set(df_v["Fecha"].unique())
        fechas_ya_auditadas = set(df_c["Fecha"].astype(str).unique()) if not df_c.empty else set()
        
        pendientes = sorted(list(fechas_con_venta - fechas_ya_auditadas), reverse=True)

        if not pendientes:
            st.success("✅ No hay cierres de ventas pendientes por auditar.")
        else:
            c1, c2 = st.columns([2, 1])
            fecha_sel = c1.selectbox("📋 Selecciona el cierre de ventas para auditar:", pendientes)
            
            # --- PASO B: DESGLOSE DETALLADO DE VENTAS DEL DÍA ---
            df_v_dia = df_v[df_v["Fecha"] == fecha_sel].copy()
            df_v_dia["Total_Dinero"] = pd.to_numeric(df_v_dia["Total_Dinero"], errors='coerce').fillna(0)
            
            # Metodologías (Ventas Brutas)
            v_bruta = df_v_dia["Total_Dinero"].sum()
            
            # Identificamos el método de pago auditado por el cajero en el módulo ventas
            col_metodo = "Metodo_Pago_Real_Auditado" if "Metodo_Pago_Real_Auditado" in df_v_dia.columns else "Metodo_Pago_Loyverse"
            
            v_efectivo = df_v_dia[df_v_dia[col_metodo] == "Efectivo"]["Total_Dinero"].sum()
            v_digital = df_v_dia[df_v_dia[col_metodo].str.contains("Nequi|Davi|Transf", case=False, na=False)]["Total_Dinero"].sum()
            v_tarjeta = df_v_dia[df_v_dia[col_metodo] == "Tarjeta"]["Total_Dinero"].sum()

            # --- PASO C: RELACIÓN AUTOMÁTICA CON GASTOS ---
            df_g["Fecha"] = df_g["Fecha"].astype(str)
            # Filtramos gastos de ese día pagados en EFECTIVO (que salen de la caja)
            gastos_dia = df_g[(df_g["Fecha"] == fecha_sel) & (df_g["Metodo"].str.contains("Efectivo", case=False, na=False))].copy()
            gastos_dia["Monto"] = pd.to_numeric(gastos_dia["Monto"], errors='coerce').fillna(0)
            total_gastos_caja = gastos_dia["Monto"].sum()

            # --- PASO D: RESULTADO TEÓRICO (DEBE HABER) ---
            debe_haber_caja = v_efectivo - total_gastos_caja

            # --- INTERFAZ VISUAL ---
            st.markdown(f"### 🛡️ Auditoría del Día: {fecha_sel}")
            
            # Fila 1: Resumen de Ventas
            st.markdown("#### 💰 Resumen de Ingresos")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("VENTA BRUTA", formato_moneda(v_bruta))
            m2.metric("Efectivo (Entrada)", formato_moneda(v_efectivo))
            m3.metric("Digital/Nequi", formato_moneda(v_digital))
            m4.metric("Tarjetas", formato_moneda(v_tarjeta))

            # Fila 2: Gastos y Saldo Caja
            st.markdown("#### 💸 Descuentos de Caja (Gastos)")
            g1, g2 = st.columns(2)
            g1.metric("Gastos Reportados (Efectivo)", f"- {formato_moneda(total_gastos_caja)}", delta_color="inverse")
            g2.metric("SALDO ESPERADO EN CAJA", formato_moneda(debe_haber_caja))

            if not gastos_dia.empty:
                with st.expander("👁️ Ver detalle de gastos que se descontaron"):
                    st.table(gastos_dia[["Concepto", "Monto", "Responsable"]])

            # Desglose de Productos
            with st.expander("📦 Ver desglose de productos vendidos en este turno"):
                resumen_prod = df_v_dia.groupby("Nombre_Plato")["Total_Dinero"].sum().reset_index().sort_values("Total_Dinero", ascending=False)
                st.dataframe(resumen_prod, use_container_width=True, hide_index=True)

            st.markdown("---")

            # --- PASO E: ENTRADA DEL DINERO REAL (AUDITORÍA) ---
            st.markdown("#### ⚖️ Validación Física vs Sistema")
            cc1, cc2 = st.columns(2)
            efectivo_fisico = cc1.number_input("💵 Efectivo Físico entregado por Cajero:", min_value=0.0, step=500.0)
            z_report = cc2.text_input("📑 Número de Z-Report / Comprobante:")

            diferencia = efectivo_fisico - debe_haber_caja
            
            if diferencia == 0:
                st.success("### ✅ CAJA CORRECTA")
            elif diferencia > 0:
                st.info(f"### 🔵 SOBRANTE EN CAJA: {formato_moneda(diferencia)}")
            else:
                st.error(f"### 🔴 FALTANTE EN CAJA: {formato_moneda(diferencia)}")

            # --- PASO F: BANCO PROFIT (AHORRO) ---
            st.markdown("---")
            st.markdown("#### 🐷 Plan de Ahorro (Profit First)")
            pct_ahorro = st.slider("% a ahorrar de la Venta Bruta", 1, 15, 5)
            monto_ahorro = v_bruta * (pct_ahorro / 100)
            st.warning(f"Se enviará una orden de ahorro al Banco Profit por: **{formato_moneda(monto_ahorro)}**")

            notas = st.text_area("Observaciones de la auditoría (Ej: El cajero olvidó registrar un gasto)")

            if st.button("🔒 FINALIZAR Y GUARDAR AUDITORÍA", type="primary", use_container_width=True):
                # Estructura para LOG_CIERRES_CAJA
                datos_cierre = [
                    fecha_sel,
                    datetime.now(ZONA_HORARIA).strftime("%H:%M"),
                    debe_haber_caja,
                    efectivo_fisico,
                    diferencia,
                    v_digital,
                    v_tarjeta,
                    notas,
                    monto_ahorro,
                    "Pendiente", # Estado para Banco Profit
                    z_report
                ]
                
                try:
                    sheet.worksheet(HOJA_CIERRES).append_row(datos_cierre)
                    st.balloons()
                    st.success("¡Turno auditado! Los datos de ahorro ya están disponibles en el Banco Profit.")
                    time.sleep(2)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

    with tab_hist:
        st.subheader("📜 Historial de Turnos Auditados")
        if not df_c.empty:
            df_c_view = df_c.copy()
            df_c_view["Diferencia"] = pd.to_numeric(df_c_view["Diferencia"], errors='coerce').fillna(0)
            
            def style_diff(v):
                color = 'red' if v < 0 else ('green' if v == 0 else 'blue')
                return f'color: {color}; font-weight: bold'

            st.dataframe(
                df_c_view[["Fecha", "Saldo_Real_Con", "Diferencia", "Profit_Retenido", "Estado_Ahorro", "Numero_Cierre_Loyverse"]]
                .style.applymap(style_diff, subset=["Diferencia"]),
                use_container_width=True, hide_index=True
            )
        else:
            st.info("Aún no hay turnos auditados.")

    with tab_dash:
        st.subheader("📊 Análisis de Operación y Cuadres")
        if not df_c.empty:
            df_d = df_c.copy()
            df_d["Diferencia"] = pd.to_numeric(df_d["Diferencia"], errors='coerce').fillna(0)
            df_d["Profit_Retenido"] = pd.to_numeric(df_d["Profit_Retenido"], errors='coerce').fillna(0)
            df_d["Saldo_Real_Con"] = pd.to_numeric(df_d["Saldo_Real_Con"], errors='coerce').fillna(0)

            c1, c2, c3 = st.columns(3)
            c1.metric("Total Efectivo Recibido", formato_moneda(df_d["Saldo_Real_Con"].sum()))
            
            total_dif = df_d["Diferencia"].sum()
            c2.metric("Balance de Cuadre", formato_moneda(total_dif), 
                      delta="Sobrante" if total_dif >= 0 else "Faltante",
                      delta_color="normal" if total_dif >= 0 else "inverse")
            
            c3.metric("Ahorro Total Generado", formato_moneda(df_d["Profit_Retenido"].sum()))

            # Gráfico de barras de diferencias
            fig = px.bar(df_d, x="Fecha", y="Diferencia", title="Desempeño de Caja por Día",
                         color="Diferencia", color_continuous_scale="RdBu", text_auto=True)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.write("Datos insuficientes para el Dashboard.")
