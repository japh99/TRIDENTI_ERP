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

def cargar_datos_maestros(sheet):
    try:
        df_v = leer_datos_seguro(sheet.worksheet(HOJA_VENTAS))
        df_g = leer_datos_seguro(sheet.worksheet(HOJA_GASTOS))
        df_c = leer_datos_seguro(sheet.worksheet(HOJA_CIERRES))
        return df_v, df_g, df_c
    except Exception as e:
        st.error(f"Error cargando bases de datos: {e}")
        return None, None, None

def show(sheet):
    st.title("🔐 Tesorería: Auditoría Final")
    
    df_v, df_g, df_c = cargar_datos_maestros(sheet)
    if df_v is None: return

    tab_audit, tab_hist, tab_dash = st.tabs(["🔎 REALIZAR AUDITORÍA", "📜 HISTORIAL", "📊 DASHBOARD"])

    with tab_audit:
        # 1. FILTRAR FECHAS DISPONIBLES (Ventas que no tienen cierre aún)
        df_v["Fecha"] = df_v["Fecha"].astype(str)
        fechas_con_ventas = set(df_v["Fecha"].unique())
        
        fechas_ya_auditadas = set()
        if not df_c.empty:
            fechas_ya_auditadas = set(df_c["Fecha"].astype(str).unique())
        
        fechas_pendientes = sorted(list(fechas_con_ventas - fechas_ya_auditadas), reverse=True)

        if not fechas_pendientes:
            st.success("✅ No hay turnos pendientes por auditar. ¡Todo al día!")
        else:
            fecha_sel = st.selectbox("📅 Selecciona el turno a auditar:", fechas_pendientes)
            
            # --- CÁLCULOS DE VENTAS ---
            ventas_dia = df_v[df_v["Fecha"] == fecha_sel].copy()
            # Usamos el método de pago auditado por el cajero en el módulo Ventas
            col_metodo = "Metodo_Pago_Real_Auditado" if "Metodo_Pago_Real_Auditado" in ventas_dia.columns else "Metodo_Pago_Loyverse"
            
            ventas_dia["Total_Dinero"] = pd.to_numeric(ventas_dia["Total_Dinero"], errors='coerce').fillna(0)
            
            v_total = ventas_dia["Total_Dinero"].sum()
            v_efectivo = ventas_dia[ventas_dia[col_metodo] == "Efectivo"]["Total_Dinero"].sum()
            v_nequi = ventas_dia[ventas_dia[col_metodo] == "Nequi"]["Total_Dinero"].sum()
            v_tarjeta = ventas_dia[ventas_dia[col_metodo] == "Tarjeta"]["Total_Dinero"].sum()

            # --- CÁLCULOS DE GASTOS (SALIDAS DE CAJA) ---
            df_g["Fecha"] = df_g["Fecha"].astype(str)
            # Buscamos gastos de esa fecha pagados en EFECTIVO
            gastos_dia = df_g[(df_g["Fecha"] == fecha_sel) & (df_g["Metodo"].str.contains("Efectivo", case=False, na=False))].copy()
            gastos_dia["Monto"] = pd.to_numeric(gastos_dia["Monto"], errors='coerce').fillna(0)
            total_gastos_caja = gastos_dia["Monto"].sum()

            # --- RESULTADO TEÓRICO ---
            debe_haber = v_efectivo - total_gastos_caja

            st.markdown(f"### Resumen de Turno: {fecha_sel}")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Venta Bruta", formato_moneda(v_total))
            c2.metric("Entradas Efectivo", formato_moneda(v_efectivo))
            c3.metric("Gastos en Efectivo", f"- {formato_moneda(total_gastos_caja)}", delta_color="inverse")
            c4.metric("DEBE HABER (Caja)", formato_moneda(debe_haber))

            if not gastos_dia.empty:
                with st.expander("📝 Detalle de gastos pagados con dinero de la caja"):
                    st.table(gastos_dia[["Concepto", "Monto", "Responsable"]])

            st.markdown("---")
            
            # --- ENTRADA DE DATOS REALES ---
            cc1, cc2 = st.columns(2)
            efectivo_fisico = cc1.number_input("💰 ¿Cuánto efectivo entregó el cajero?", min_value=0.0, step=500.0)
            z_report = cc2.text_input("📑 Número de Z-Report / Factura Final")

            # SEMÁFORO DE DIFERENCIA
            diferencia = efectivo_fisico - debe_haber
            
            if diferencia == 0:
                st.success(f"### ✅ CAJA CUADRADA EXAСТА")
            elif diferencia > 0:
                st.info(f"### 🔵 SOBRANTE: {formato_moneda(diferencia)}")
            else:
                st.error(f"### 🔴 FALTANTE: {formato_moneda(diferencia)}")

            # --- AHORRO PARA BANCO PROFIT ---
            st.markdown("### 🐷 Reserva de Utilidad (Profit)")
            pct_ahorro = st.slider("% a ahorrar sobre la venta total", 1, 15, 5)
            monto_ahorro = v_total * (pct_ahorro / 100)
            st.warning(f"Se generará una orden de ahorro por: **{formato_moneda(monto_ahorro)}**")

            notas = st.text_area("Notas / Observaciones de la auditoría")

            if st.button("🔒 GUARDAR AUDITORÍA Y CERRAR TURNO", type="primary", use_container_width=True):
                # Preparar datos según tus encabezados de LOG_CIERRES_CAJA
                # Fecha, Hora, Saldo_Teorico_E, Saldo_Real_Con, Diferencia, Total_Nequi, Total_Tarjetas, Notas, Profit_Retenido, Estado_Ahorro, Numero_Cierre_Loyverse
                datos_finales = [
                    fecha_sel,
                    datetime.now(ZONA_HORARIA).strftime("%H:%M"),
                    debe_haber,
                    efectivo_fisico,
                    diferencia,
                    v_nequi,
                    v_tarjeta,
                    notas,
                    monto_ahorro,
                    "Pendiente", # Esto lo lee el Banco Profit
                    z_report
                ]
                
                try:
                    sheet.worksheet(HOJA_CIERRES).append_row(datos_finales)
                    st.balloons()
                    st.success("Cierre guardado exitosamente. Los datos se han sincronizado con el Banco Profit.")
                    time.sleep(2)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

    with tab_hist:
        st.subheader("📜 Historial de Turnos Auditados")
        if not df_c.empty:
            df_c_ver = df_c.copy()
            df_c_ver["Diferencia"] = pd.to_numeric(df_c_ver["Diferencia"], errors='coerce').fillna(0)
            
            def color_semaforo(val):
                color = 'red' if val < 0 else ('green' if val == 0 else 'blue')
                return f'color: {color}; font-weight: bold'

            st.dataframe(
                df_c_ver[["Fecha", "Saldo_Real_Con", "Diferencia", "Profit_Retenido", "Estado_Ahorro", "Numero_Cierre_Loyverse"]]
                .style.applymap(color_semaforo, subset=["Diferencia"]),
                use_container_width=True, hide_index=True
            )
        else:
            st.info("No hay historial disponible.")

    with tab_dash:
        st.subheader("📊 Análisis de Rendimiento de Caja")
        if not df_c.empty:
            df_dash = df_c.copy()
            df_dash["Diferencia"] = pd.to_numeric(df_dash["Diferencia"], errors='coerce').fillna(0)
            df_dash["Profit_Retenido"] = pd.to_numeric(df_dash["Profit_Retenido"], errors='coerce').fillna(0)
            df_dash["Saldo_Real_Con"] = pd.to_numeric(df_dash["Saldo_Real_Con"], errors='coerce').fillna(0)

            c1, c2, c3 = st.columns(3)
            c1.metric("Efectivo Total Auditado", formato_moneda(df_dash["Saldo_Real_Con"].sum()))
            
            diff_total = df_dash["Diferencia"].sum()
            c2.metric("Balance de Descuadres", formato_moneda(diff_total), 
                      delta="Sobrante" if diff_total >= 0 else "Faltante", 
                      delta_color="normal" if diff_total >= 0 else "inverse")
            
            c3.metric("Ahorro Total Proyectado", formato_moneda(df_dash["Profit_Retenido"].sum()))

            # Gráfico de barras de diferencias diarias
            fig = px.bar(df_dash, x="Fecha", y="Diferencia", 
                         title="Sobrantes y Faltantes por Día",
                         color="Diferencia", color_continuous_scale="RdBu")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Aún no hay datos para mostrar gráficos.")
