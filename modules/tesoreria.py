import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import time
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero, generar_id

# --- CONFIGURACIÓN ---
HOJA_VENTAS = "LOG_VENTAS_LOYVERSE"
HOJA_GASTOS = "LOG_PAGOS_GASTOS"
HOJA_CIERRES = "LOG_CIERRES_CAJA"

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

def show(sheet):
    st.title("🔐 Tesorería: Auditoría por Cierres")
    st.caption("Selecciona un cierre de ventas específico para validar la caja y programar ahorros.")

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

    tab_audit, tab_hist, tab_dash = st.tabs(["🔎 AUDITAR CIERRE", "📜 HISTORIAL", "📊 DASHBOARD"])

    with tab_audit:
        # --- PASO A: IDENTIFICAR LOS CIERRES DISPONIBLES EN VENTAS ---
        # Buscamos la columna que identifica el cierre (ajusta el nombre si es distinto)
        col_cierre = "Numero_Cierre_Loyverse" if "Numero_Cierre_Loyverse" in df_v.columns else "ID_Cierre"
        
        if col_cierre not in df_v.columns:
            st.error(f"No se encontró la columna de identificación de cierre '{col_cierre}' en Ventas.")
            return

        # Obtenemos los IDs de cierre únicos que NO están en la hoja de Tesorería
        cierres_en_ventas = df_v[df_v[col_cierre] != ""][col_cierre].unique().tolist()
        cierres_ya_auditados = df_c["Numero_Cierre_Loyverse"].astype(str).unique().tolist() if not df_c.empty else []
        
        pendientes = [str(c) for c in cierres_en_ventas if str(c) not in cierres_ya_auditados]

        if not pendientes:
            st.success("✅ ¡Excelente! No hay cierres de caja pendientes por auditar.")
        else:
            # Crear una lista amigable: "Cierre #123 | 2025-12-21 | $ 500.000"
            df_v["Total_Dinero"] = pd.to_numeric(df_v["Total_Dinero"], errors='coerce').fillna(0)
            
            opciones_label = []
            for p in pendientes:
                data_temp = df_v[df_v[col_cierre].astype(str) == p]
                fecha_c = data_temp["Fecha"].iloc[0]
                total_c = data_temp["Total_Dinero"].sum()
                opciones_label.append(f"Cierre #{p} | {fecha_c} | {formato_moneda(total_c)}")

            seleccion = st.selectbox("📋 Selecciona el cierre de ventas para auditar:", opciones_label)
            
            if seleccion:
                cierre_id = seleccion.split(" | ")[0].replace("Cierre #", "")
                
                # --- PASO B: FILTRAR DATOS DE ESTE CIERRE ESPECÍFICO ---
                df_cierre_sel = df_v[df_v[col_cierre].astype(str) == cierre_id].copy()
                fecha_cierre = df_cierre_sel["Fecha"].iloc[0]
                
                # Totales de Ventas
                v_bruta = df_cierre_sel["Total_Dinero"].sum()
                v_efectivo = df_cierre_sel[df_cierre_sel["Metodo_Pago_Real_Auditado"] == "Efectivo"]["Total_Dinero"].sum()
                v_digital = df_cierre_sel[df_cierre_sel["Metodo_Pago_Real_Auditado"].str.contains("Nequi|Davi|Transf", case=False, na=False)]["Total_Dinero"].sum()
                v_tarjetas = df_cierre_sel[df_cierre_sel["Metodo_Pago_Real_Auditado"] == "Tarjeta"]["Total_Dinero"].sum()

                # --- PASO C: RELACIÓN CON GASTOS (POR FECHA DEL CIERRE) ---
                df_g["Fecha"] = df_g["Fecha"].astype(str)
                gastos_dia = df_g[(df_g["Fecha"] == str(fecha_cierre)) & (df_g["Metodo"].str.contains("Efectivo", case=False, na=False))].copy()
                gastos_dia["Monto"] = pd.to_numeric(gastos_dia["Monto"], errors='coerce').fillna(0)
                total_gastos = gastos_dia["Monto"].sum()

                # --- PASO D: RESULTADO SISTEMA ---
                debe_haber = v_efectivo - total_gastos

                # INTERFAZ
                st.markdown(f"### 🛡️ Auditoría del {seleccion}")
                
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Venta Bruta", formato_moneda(v_bruta))
                k2.metric("Entradas Efectivo", formato_moneda(v_efectivo))
                k3.metric("Gastos Pagados", f"- {formato_moneda(total_gastos)}", delta_color="inverse")
                k4.metric("DEBE HABER (Caja)", formato_moneda(debe_haber))

                with st.expander("📦 Desglose de Ventas"):
                    resumen_prod = df_cierre_sel.groupby("Nombre_Plato")["Total_Dinero"].sum().reset_index().sort_values("Total_Dinero", ascending=False)
                    st.table(resumen_prod)

                if not gastos_dia.empty:
                    with st.expander("💸 Detalle de Gastos Descontados"):
                        st.table(gastos_dia[["Concepto", "Monto", "Responsable"]])

                st.markdown("---")
                
                # VALIDACIÓN REAL
                cc1, cc2 = st.columns(2)
                efectivo_fisico = cc1.number_input("💵 Efectivo Real Entregado:", min_value=0.0, step=500.0)
                z_report = cc2.text_input("📑 Z-Report / Comprobante Final:", value=cierre_id)

                diferencia = efectivo_fisico - debe_haber
                
                if diferencia == 0: st.success("### ✅ CAJA CUADRADA")
                elif diferencia > 0: st.info(f"### 🔵 SOBRANTE: {formato_moneda(diferencia)}")
                else: st.error(f"### 🔴 FALTANTE: {formato_moneda(diferencia)}")

                # AHORRO
                st.markdown("#### 🐷 Reserva para Banco Profit")
                pct = st.slider("% Ahorro Sugerido", 1, 15, 5)
                ahorro = v_bruta * (pct / 100)
                st.warning(f"Se enviará una orden de ahorro por: **{formato_moneda(ahorro)}**")

                notas = st.text_area("Notas de la auditoría:")

                if st.button("🔒 FINALIZAR AUDITORÍA Y CERRAR TURNO", type="primary", use_container_width=True):
                    # Guardar en LOG_CIERRES_CAJA
                    datos = [
                        fecha_cierre, 
                        datetime.now(ZONA_HORARIA).strftime("%H:%M"),
                        debe_haber,
                        efectivo_fisico,
                        diferencia,
                        v_digital,
                        v_tarjetas,
                        notas,
                        ahorro,
                        "Pendiente",
                        z_report
                    ]
                    try:
                        sheet.worksheet(HOJA_CIERRES).append_row(datos)
                        st.balloons(); st.success("Cierre Guardado."); time.sleep(2); st.rerun()
                    except Exception as e: st.error(f"Error: {e}")

    with tab_hist:
        st.subheader("📜 Historial de Cierres Auditados")
        if not df_c.empty:
            df_c["Diferencia"] = pd.to_numeric(df_c["Diferencia"], errors='coerce').fillna(0)
            def color_semaforo(v):
                return f'color: {"red" if v < 0 else ("green" if v == 0 else "blue")}; font-weight: bold'
            
            st.dataframe(
                df_c[["Fecha", "Saldo_Real_Con", "Diferencia", "Profit_Retenido", "Numero_Cierre_Loyverse"]]
                .style.applymap(color_semaforo, subset=["Diferencia"]),
                use_container_width=True, hide_index=True
            )

    with tab_dash:
        st.subheader("📊 Dashboard de Control")
        if not df_c.empty:
            df_d = df_c.copy()
            df_d["Diferencia"] = pd.to_numeric(df_d["Diferencia"], errors='coerce').fillna(0)
            df_d["Profit_Retenido"] = pd.to_numeric(df_d["Profit_Retenido"], errors='coerce').fillna(0)
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Efectivo Auditado", formato_moneda(pd.to_numeric(df_d["Saldo_Real_Con"], errors='coerce').sum()))
            c2.metric("Acumulado Diferencias", formato_moneda(df_d["Diferencia"].sum()))
            c3.metric("Total Ahorros Generados", formato_moneda(df_d["Profit_Retenido"].sum()))
            
            fig = px.line(df_d, x="Fecha", y="Diferencia", title="Tendencia de Descuadres", markers=True)
            st.plotly_chart(fig, use_container_width=True)
