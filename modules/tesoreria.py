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
    st.caption("Sincronización basada en Shift_ID de Loyverse.")

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

    # --- NOMBRE EXACTO DE LA COLUMNA SEGÚN TU IMAGEN ---
    col_identificador = "Shift_ID" 

    tab_audit, tab_hist, tab_dash = st.tabs(["🔎 AUDITAR TURNO", "📜 HISTORIAL", "📊 DASHBOARD"])

    with tab_audit:
        # Identificamos los Shifts que NO han sido auditados aún
        # Convertimos a string para evitar errores de comparación
        df_v[col_identificador] = df_v[col_identificador].astype(str)
        
        # Obtenemos lista de todos los turnos en ventas
        todos_los_shifts = [s for s in df_v[col_identificador].unique() if s and s != "nan" and s != "None"]
        
        # Obtenemos los ya auditados de la hoja de cierres
        auditados = []
        if not df_c.empty and "Numero_Cierre_Loyverse" in df_c.columns:
            auditados = df_c["Numero_Cierre_Loyverse"].astype(str).unique().tolist()
        
        # Turnos que faltan
        pendientes = [s for s in todos_los_shifts if s not in auditados]

        if not pendientes:
            st.success("✅ ¡Todos los turnos (Shifts) están auditados!")
        else:
            # Preparamos las opciones para el selectbox
            df_v["Total_Dinero"] = pd.to_numeric(df_v["Total_Dinero"], errors='coerce').fillna(0)
            
            opciones_label = []
            for s in pendientes:
                data_shift = df_v[df_v[col_identificador] == s]
                fecha_shift = data_shift["Fecha"].iloc[0]
                total_shift = data_shift["Total_Dinero"].sum()
                # Mostramos: "ID Corto | Fecha | Total"
                opciones_label.append(f"{s[:8]}... | {fecha_shift} | {formato_moneda(total_shift)}")

            seleccion_label = st.selectbox("📋 Selecciona el Turno (Shift) a auditar:", opciones_label)
            
            if seleccion_label:
                # Recuperamos el ID real buscando el match en la lista original
                idx_sel = opciones_label.index(seleccion_label)
                shift_id_real = pendientes[idx_sel]
                
                # --- FILTRAR DATOS DE ESTE SHIFT ---
                df_sel = df_v[df_v[col_identificador] == shift_id_real].copy()
                fecha_turno = df_sel["Fecha"].iloc[0]
                
                # Totales
                v_bruta = df_sel["Total_Dinero"].sum()
                v_efectivo = df_sel[df_sel["Metodo_Pago_Real_Auditado"] == "Efectivo"]["Total_Dinero"].sum()
                v_digital = df_sel[df_sel["Metodo_Pago_Real_Auditado"].str.contains("Nequi|Davi|Transf", case=False, na=False)]["Total_Dinero"].sum()
                v_tarjetas = df_sel[df_sel["Metodo_Pago_Real_Auditado"] == "Tarjeta"]["Total_Dinero"].sum()

                # --- RELACIÓN CON GASTOS (Basada en la fecha del turno) ---
                df_g["Fecha"] = df_g["Fecha"].astype(str)
                gastos_dia = df_g[(df_g["Fecha"] == str(fecha_turno)) & (df_g["Metodo"].str.contains("Efectivo", case=False, na=False))].copy()
                gastos_dia["Monto"] = pd.to_numeric(gastos_dia["Monto"], errors='coerce').fillna(0)
                total_gastos = gastos_dia["Monto"].sum()

                # --- RESULTADO SISTEMA ---
                debe_haber = v_efectivo - total_gastos

                st.markdown(f"### 🛡️ Auditoría Turno: `{shift_id_real}`")
                
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Venta Bruta", formato_moneda(v_bruta))
                k2.metric("Entradas Efectivo", formato_moneda(v_efectivo))
                k3.metric("Gastos en Efectivo", f"- {formato_moneda(total_gastos)}", delta_color="inverse")
                k4.metric("DEBE HABER CAJA", formato_moneda(debe_haber))

                with st.expander("📦 Desglose de Productos Vendidos"):
                    resumen = df_sel.groupby("Nombre_Plato")["Total_Dinero"].sum().reset_index().sort_values("Total_Dinero", ascending=False)
                    st.table(resumen)

                st.markdown("---")
                
                # VALIDACIÓN REAL
                cc1, cc2 = st.columns(2)
                efectivo_fisico = cc1.number_input("💵 Efectivo Físico Contado:", min_value=0.0, step=500.0)
                z_report = cc2.text_input("📑 Z-Report / Comprobante:", value=shift_id_real[:10])

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

                if st.button("🔒 GUARDAR Y CERRAR TURNO", type="primary", use_container_width=True):
                    # Fecha, Hora, Teórico, Real, Dif, Digital, Tarjeta, Notas, Ahorro, Estado, ID_Loyverse
                    datos = [
                        fecha_turno, 
                        datetime.now(ZONA_HORARIA).strftime("%H:%M"),
                        debe_haber,
                        efectivo_fisico,
                        diferencia,
                        v_digital,
                        v_tarjetas,
                        notas,
                        ahorro,
                        "Pendiente",
                        shift_id_real # Guardamos el Shift_ID aquí para que desaparezca de pendientes
                    ]
                    try:
                        sheet.worksheet(HOJA_CIERRES).append_row(datos)
                        st.balloons(); st.success("Auditado correctamente."); time.sleep(2); st.rerun()
                    except Exception as e: st.error(f"Error: {e}")

    with tab_hist:
        st.subheader("📜 Historial de Turnos Auditados")
        if not df_c.empty:
            st.dataframe(df_c[["Fecha", "Saldo_Real_Con", "Diferencia", "Profit_Retenido", "Numero_Cierre_Loyverse"]], use_container_width=True, hide_index=True)

    with tab_dash:
        st.subheader("📊 Análisis de Diferencias")
        if not df_c.empty:
            df_c["Diferencia"] = pd.to_numeric(df_c["Diferencia"], errors='coerce').fillna(0)
            fig = px.bar(df_c, x="Fecha", y="Diferencia", color="Diferencia", title="Sobrantes y Faltantes por Turno")
            st.plotly_chart(fig, use_container_width=True)
