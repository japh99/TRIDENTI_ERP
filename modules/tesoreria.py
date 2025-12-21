import streamlit as st
import pandas as pd
from datetime import datetime
import time
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero, generar_id

# --- CONFIGURACIÓN DE HOJAS ---
HOJA_VENTAS = "LOG_VENTAS_LOYVERSE"
HOJA_GASTOS = "LOG_PAGOS_GASTOS"
HOJA_CIERRES = "LOG_CIERRES_CAJA"

# Encabezados exactos según tu base de datos
HEADERS_CIERRE = [
    "Fecha", "Hora_Cierre", "Saldo_Teorico_E", "Saldo_Real_Con", 
    "Diferencia", "Total_Nequi", "Total_Tarjetas", "Notas", 
    "Profit_Retenido", "Estado_Ahorro", "Numero_Cierre_Loyverse"
]

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

# --- FUNCIONES DE CARGA ---

def cargar_movimientos_desglosados(sheet, fecha_str):
    try:
        ws_v = sheet.worksheet(HOJA_VENTAS)
        df_raw = leer_datos_seguro(ws_v)
        
        if not df_raw.empty:
            df_raw["Fecha"] = df_raw["Fecha"].astype(str)
            df_dia = df_raw[df_raw["Fecha"] == fecha_str].copy()
            df_dia["Total_Dinero"] = pd.to_numeric(df_dia["Total_Dinero"], errors='coerce').fillna(0)
            
            # Agrupar por Recibo para manejar el ticket completo (API Loyverse)
            df_grouped = df_dia.groupby("Numero_Recibo").agg({
                "Total_Dinero": "sum",
                "Metodo_Pago_Loyverse": "first",
                "Hora": "first"
            }).reset_index()

            # Inicializar desglose: ponemos el total en la columna que reportó el cajero originalmente
            df_grouped["Efectivo_Real"] = df_grouped.apply(lambda x: x["Total_Dinero"] if x["Metodo_Pago_Loyverse"] == "Efectivo" else 0.0, axis=1)
            df_grouped["Nequi_Real"] = df_grouped.apply(lambda x: x["Total_Dinero"] if "Nequi" in str(x["Metodo_Pago_Loyverse"]) else 0.0, axis=1)
            df_grouped["Tarjeta_Real"] = df_grouped.apply(lambda x: x["Total_Dinero"] if "Tarjeta" in str(x["Metodo_Pago_Loyverse"]) else 0.0, axis=1)
            
            return df_grouped, ws_v
        return pd.DataFrame(), None
    except Exception as e:
        st.error(f"Error cargando ventas: {e}")
        return None, None

# --- INTERFAZ ---

def show(sheet):
    st.title("🔐 Tesorería: Cierre de Caja")
    st.caption("Auditoría de tickets, desgloses de pago y arqueo físico.")
    
    if not sheet: return

    hoy = datetime.now(ZONA_HORARIA).date()
    fecha_cierre = st.date_input("Fecha de Trabajo", value=hoy)
    fecha_str = fecha_cierre.strftime("%Y-%m-%d")

    # 1. VERIFICAR SI YA EXISTE UN CIERRE
    ws_c = sheet.worksheet(HOJA_CIERRES)
    df_c = leer_datos_seguro(ws_c)
    cierre_previo = None
    if not df_c.empty and "Fecha" in df_c.columns:
        res = df_c[df_c["Fecha"] == fecha_str]
        if not res.empty: cierre_previo = res.iloc[0]

    if cierre_previo is not None:
        # --- MODO LECTURA: DÍA CERRADO ---
        st.success(f"✅ DÍA CERRADO - Z-Report: {cierre_previo.get('Numero_Cierre_Loyverse', 'S/N')}")
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Efectivo Contado", formato_moneda(cierre_previo['Saldo_Real_Con']))
        
        diff = float(limpiar_numero(cierre_previo['Diferencia']))
        c2.metric("Diferencia", formato_moneda(diff), delta=diff, delta_color="normal")
        
        c3.metric("Nequi", formato_moneda(cierre_previo['Total_Nequi']))
        c4.metric("Tarjetas", formato_moneda(cierre_previo['Total_Tarjetas']))
        
        st.info(f"**Notas:** {cierre_previo.get('Notas', 'Sin notas adicionales.')}")

    else:
        # --- MODO EDICIÓN: PROCESAR CIERRE ---
        df_tickets, ws_v = cargar_movimientos_desglosados(sheet, fecha_str)
        
        if df_tickets is None or df_tickets.empty:
            st.warning("No hay ventas registradas para esta fecha.")
        else:
            # 1. TABLA DE AUDITORÍA CON DESGLOSE MIXTO
            with st.expander("🛠️ Auditoría de Tickets (Pagos Mixtos y Correcciones)", expanded=True):
                st.write("Si un pago fue dividido (ej: mitad Nequi, mitad Efectivo), reparte el monto en las columnas.")
                
                # Columna de validación visual
                df_tickets["Suma_Auditada"] = df_tickets["Efectivo_Real"] + df_tickets["Nequi_Real"] + df_tickets["Tarjeta_Real"]
                
                df_ed = st.data_editor(
                    df_tickets[["Hora", "Numero_Recibo", "Total_Dinero", "Efectivo_Real", "Nequi_Real", "Tarjeta_Real", "Suma_Auditada"]],
                    column_config={
                        "Total_Dinero": st.column_config.NumberColumn("Valor Ticket", format="$%d", disabled=True),
                        "Efectivo_Real": st.column_config.NumberColumn("Efectivo $", format="$%d", min_value=0.0),
                        "Nequi_Real": st.column_config.NumberColumn("Nequi $", format="$%d", min_value=0.0),
                        "Tarjeta_Real": st.column_config.NumberColumn("Tarjeta $", format="$%d", min_value=0.0),
                        "Suma_Auditada": st.column_config.NumberColumn("Validación", format="$%d", disabled=True),
                        "Numero_Recibo": "Ticket #"
                    },
                    hide_index=True, use_container_width=True, key="editor_mixto_v3"
                )

                # Verificar si algún ticket no cuadra
                df_ed["Dif_Validar"] = abs(df_ed["Total_Dinero"] - (df_ed["Efectivo_Real"] + df_ed["Nequi_Real"] + df_ed["Tarjeta_Real"]))
                error_validacion = df_ed[df_ed["Dif_Validar"] > 1]
                
                if not error_validacion.empty:
                    st.error(f"🚨 Tienes {len(error_validacion)} tickets que no cuadran con el total. Ajusta los valores.")

            # 2. CÁLCULOS DINÁMICOS BASADOS EN EL EDITOR
            v_total = df_ed["Total_Dinero"].sum()
            v_efec = df_ed["Efectivo_Real"].sum()
            v_nequi = df_ed["Nequi_Real"].sum()
            v_tarj = df_ed["Tarjeta_Real"].sum()
            
            # Gastos de Caja (de la hoja de gastos)
            try:
                ws_g = sheet.worksheet(HOJA_GASTOS)
                df_g = leer_datos_seguro(ws_g)
                g_efec = df_g[(df_g["Fecha"] == fecha_str) & (df_g["Metodo_Pago"].str.contains("Efectivo", na=False))]["Monto"].astype(float).sum()
            except: g_efec = 0
            
            saldo_teo = v_efec - g_efec

            # --- PANEL DE RESUMEN ---
            st.markdown("#### 📊 Resumen Financiero Auditado")
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("VENTA TOTAL", formato_moneda(v_total))
            k2.metric("Total Efectivo", formato_moneda(v_efec))
            k3.metric("Total Nequi", formato_moneda(v_nequi))
            k4.metric("Total Tarjetas", formato_moneda(v_tarj))

            st.markdown("---")
            st.markdown("#### 💵 Arqueo de Efectivo")
            a1, a2, a3 = st.columns(3)
            a1.metric("(+) Entradas Efec.", formato_moneda(v_efec))
            a2.metric("(-) Gastos Caja", formato_moneda(g_efec))
            a3.metric("(=) DEBE HABER", formato_moneda(saldo_teo))

            # ENTRADA DE DATOS
            c_real, c_z = st.columns(2)
            real = c_real.number_input("¿Cuánto efectivo contaste físicamente?", min_value=0.0, step=500.0)
            z_rep = c_z.text_input("Z-Report / Número de Cierre Loyverse")
            
            # SEMÁFORO DE DIFERENCIA
            diff = real - saldo_teo
            if diff == 0:
                st.success(f"### ✅ CORRECTO: {formato_moneda(diff)}")
            elif diff > 0:
                st.info(f"### 🔵 SOBRANTE: {formato_moneda(diff)}")
            else:
                st.error(f"### 🔴 FALTANTE: {formato_moneda(diff)}")

            # NOTAS Y PROFIT
            pct_prof = st.slider("% Profit Sugerido", 1, 15, 5)
            monto_prof = v_total * (pct_prof / 100)
            st.info(f"💡 Sugerencia de ahorro (Profit): {formato_moneda(monto_prof)}")
            
            notas_cierre = st.text_area("Notas del Cierre")

            # BOTÓN DE GUARDADO
            if st.button("🔒 GUARDAR CIERRE DEFINITIVO", type="primary", use_container_width=True):
                if not error_validacion.empty:
                    st.warning("Corrige el desglose de los tickets antes de guardar.")
                elif not z_rep:
                    st.warning("Debes ingresar el número de Z-Report.")
                else:
                    datos_finales = {
                        "Fecha": fecha_str,
                        "Hora_Cierre": datetime.now(ZONA_HORARIA).strftime("%H:%M"),
                        "Saldo_Teorico_E": saldo_teo,
                        "Saldo_Real_Con": real,
                        "Diferencia": diff,
                        "Total_Nequi": v_nequi,
                        "Total_Tarjetas": v_tarj,
                        "Notas": notas_cierre,
                        "Profit_Retenido": monto_prof,
                        "Estado_Ahorro": "Pendiente",
                        "Numero_Cierre_Loyverse": z_rep
                    }
                    # Guardar en Google Sheets
                    nueva_fila = [str(datos_finales.get(h, "")) for h in HEADERS_CIERRE]
                    ws_c.append_row(nueva_fila)
                    st.balloons()
                    time.sleep(1)
                    st.rerun()

    # --- TABLA DE HISTORIAL (ABOJO) ---
    st.markdown("---")
    st.subheader("📜 Historial de Cierres Recientes")
    try:
        # Volvemos a leer para asegurar datos frescos
        df_hist = leer_datos_seguro(sheet.worksheet(HOJA_CIERRES))
        if not df_hist.empty:
            # Ordenar por fecha reciente
            df_hist = df_hist.sort_values("Fecha", ascending=False).head(10)
            
            # Formatear columnas de dinero para visualización
            cols_money = ["Saldo_Teorico_E", "Saldo_Real_Con", "Diferencia", "Profit_Retenido"]
            for col in cols_money:
                if col in df_hist.columns:
                    df_hist[col] = pd.to_numeric(df_hist[col], errors='coerce').apply(formato_moneda)
            
            # Mostrar solo columnas relevantes
            cols_show = ["Fecha", "Numero_Cierre_Loyverse", "Saldo_Teorico_E", "Saldo_Real_Con", "Diferencia", "Notas"]
            st.dataframe(df_hist[cols_show], use_container_width=True, hide_index=True)
        else:
            st.write("No hay cierres registrados en el historial.")
    except Exception as e:
        st.caption(f"Cargando historial... {e}")
