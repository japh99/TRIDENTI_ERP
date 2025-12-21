import streamlit as st
import pandas as pd
from datetime import datetime
import time
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero, generar_id

# --- CONFIGURACIÓN ---
HOJA_VENTAS = "LOG_VENTAS_LOYVERSE"
HOJA_GASTOS = "LOG_PAGOS_GASTOS"
HOJA_CIERRES = "LOG_CIERRES_CAJA"

HEADERS_CIERRE = [
    "Fecha", "Hora_Cierre", "Saldo_Teorico_E", "Saldo_Real_Con", 
    "Diferencia", "Total_Nequi", "Total_Tarjetas", "Notas", 
    "Profit_Retenido", "Estado_Ahorro", "Numero_Cierre_Loyverse"
]

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

# --- FUNCIONES DE DATOS ---

def cargar_movimientos_desglosados(sheet, fecha_str):
    try:
        ws_v = sheet.worksheet(HOJA_VENTAS)
        df_raw = leer_datos_seguro(ws_v)
        
        if not df_raw.empty:
            df_raw["Fecha"] = df_raw["Fecha"].astype(str)
            df_dia = df_raw[df_raw["Fecha"] == fecha_str].copy()
            df_dia["Total_Dinero"] = pd.to_numeric(df_dia["Total_Dinero"], errors='coerce').fillna(0)
            
            # Agrupamos por recibo
            df_grouped = df_dia.groupby("Numero_Recibo").agg({
                "Total_Dinero": "sum",
                "Metodo_Pago_Loyverse": "first",
                "Hora": "first"
            }).reset_index()

            # --- INICIALIZAR COLUMNAS DE DESGLOSE ---
            # Por defecto, ponemos todo el valor del ticket en el método que dice Loyverse
            df_grouped["Efectivo_Real"] = df_grouped.apply(lambda x: x["Total_Dinero"] if x["Metodo_Pago_Loyverse"] == "Efectivo" else 0.0, axis=1)
            df_grouped["Nequi_Real"] = df_grouped.apply(lambda x: x["Total_Dinero"] if "Nequi" in str(x["Metodo_Pago_Loyverse"]) else 0.0, axis=1)
            df_grouped["Tarjeta_Real"] = df_grouped.apply(lambda x: x["Total_Dinero"] if "Tarjeta" in str(x["Metodo_Pago_Loyverse"]) else 0.0, axis=1)
            
            return df_grouped, ws_v
        return pd.DataFrame(), None
    except Exception as e:
        st.error(f"Error: {e}")
        return None, None

def show(sheet):
    st.title("🔐 Tesorería: Cierre de Caja")
    if not sheet: return

    hoy = datetime.now(ZONA_HORARIA).date()
    fecha_cierre = st.date_input("Fecha de Trabajo", value=hoy)
    fecha_str = fecha_cierre.strftime("%Y-%m-%d")

    # 1. VERIFICAR CIERRE EXISTENTE
    try:
        ws_c = sheet.worksheet(HOJA_CIERRES)
        df_c = leer_datos_seguro(ws_c)
        cierre_previo = df_c[df_c["Fecha"] == fecha_str].iloc[0] if not df_c.empty and fecha_str in df_c["Fecha"].values else None
    except: cierre_previo = None

    if cierre_previo is not None:
        st.success(f"✅ DÍA CERRADO - Z-Report: {cierre_previo.get('Numero_Cierre_Loyverse', 'S/N')}")
        m1, m2, m3 = st.columns(3)
        m1.metric("Efectivo Contado", formato_moneda(cierre_previo['Saldo_Real_Con']))
        m2.metric("Diferencia", formato_moneda(cierre_previo['Diferencia']))
        m3.metric("Profit Ahorrado", formato_moneda(cierre_previo['Profit_Retenido']))
    else:
        # 2. PROCESAR NUEVO CIERRE
        df_tickets, ws_v = cargar_movimientos_desglosados(sheet, fecha_str)
        
        if df_tickets is None or df_tickets.empty:
            st.warning("No hay ventas en esta fecha.")
        else:
            # --- SECCIÓN DE AUDITORÍA CON DESGLOSE ---
            with st.expander("🛠️ Auditoría de Tickets (Soporte Pagos Mixtos)", expanded=True):
                st.info("Si un cliente pagó con dos métodos, reparte el valor en las columnas correspondientes. La 'Suma Auditada' debe ser igual al 'Valor Total'.")
                
                # Columnas de trabajo
                df_tickets["Suma_Auditada"] = df_tickets["Efectivo_Real"] + df_tickets["Nequi_Real"] + df_tickets["Tarjeta_Real"]
                
                df_ed = st.data_editor(
                    df_tickets[["Hora", "Numero_Recibo", "Total_Dinero", "Efectivo_Real", "Nequi_Real", "Tarjeta_Real", "Suma_Auditada"]],
                    column_config={
                        "Total_Dinero": st.column_config.NumberColumn("Valor Total", format="$%d", disabled=True),
                        "Efectivo_Real": st.column_config.NumberColumn("Efectivo $", format="$%d", min_value=0.0),
                        "Nequi_Real": st.column_config.NumberColumn("Nequi $", format="$%d", min_value=0.0),
                        "Tarjeta_Real": st.column_config.NumberColumn("Tarjeta $", format="$%d", min_value=0.0),
                        "Suma_Auditada": st.column_config.NumberColumn("Validación", format="$%d", disabled=True),
                        "Numero_Recibo": "Ticket #"
                    },
                    hide_index=True, use_container_width=True, key="editor_mixto"
                )

                # Validar sumas antes de seguir
                errores_suma = df_ed[abs(df_ed["Total_Dinero"] - (df_ed["Efectivo_Real"] + df_ed["Nequi_Real"] + df_ed["Tarjeta_Real"])) > 1]
                if not errores_suma.empty:
                    st.error(f"⚠️ Atención: Hay {len(errores_suma)} tickets donde el desglose no coincide con el total. Por favor verifica.")

            # --- 3. CÁLCULOS PARA DASHBOARD (USANDO DATOS DEL EDITOR) ---
            v_total = df_ed["Total_Dinero"].sum()
            v_efec = df_ed["Efectivo_Real"].sum()
            v_nequi = df_ed["Nequi_Real"].sum()
            v_tarj = df_ed["Tarjeta_Real"].sum()
            
            # Cargar Gastos
            try:
                ws_g = sheet.worksheet(HOJA_GASTOS)
                df_g = leer_datos_seguro(ws_g)
                g_efec = df_g[(df_g["Fecha"] == fecha_str) & (df_g["Metodo_Pago"].str.contains("Efectivo", na=False))]["Monto"].astype(float).sum()
            except: g_efec = 0
            
            saldo_teo = v_efec - g_efec

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

            c_real, c_z = st.columns(2)
            real = c_real.number_input("Efectivo Físico Contado:", min_value=0.0, step=500.0)
            z_rep = c_z.text_input("Z-Report / Numero Cierre")
            
            diff = real - saldo_teo
            
            if diff == 0: st.success(f"### ✅ CORRECTO: {formato_moneda(diff)}")
            elif diff > 0: st.info(f"### 🔵 SOBRANTE: {formato_moneda(diff)}")
            else: st.error(f"### 🔴 FALTANTE: {formato_moneda(diff)}")

            if st.button("🔒 GUARDAR CIERRE DEFINITIVO", type="primary", use_container_width=True):
                if not errores_suma.empty:
                    st.warning("No puedes guardar el cierre si el desglose de los tickets no es correcto.")
                else:
                    datos = {
                        "Fecha": fecha_str,
                        "Hora_Cierre": datetime.now(ZONA_HORARIA).strftime("%H:%M"),
                        "Saldo_Teorico_E": saldo_teo,
                        "Saldo_Real_Con": real,
                        "Diferencia": diff,
                        "Total_Nequi": v_nequi,
                        "Total_Tarjetas": v_tarj,
                        "Notas": f"Venta auditada. {len(df_tickets)} tickets.",
                        "Profit_Retenido": v_total * 0.05,
                        "Estado_Ahorro": "Pendiente",
                        "Numero_Cierre_Loyverse": z_rep
                    }
                    ws_c.append_row([str(datos.get(h, "")) for h in HEADERS_CIERRE])
                    st.balloons()
                    time.sleep(1)
                    st.rerun()
