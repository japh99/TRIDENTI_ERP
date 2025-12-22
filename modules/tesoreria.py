import streamlit as st
import pandas as pd
from datetime import datetime
import time
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero, generar_id

# --- CONFIGURACIÓN DE HOJAS (Coincide con tu Ventas.py) ---
HOJA_VENTAS = "LOG_VENTAS_LOYVERSE"
HOJA_GASTOS = "LOG_GASTOS"
HOJA_CIERRES = "LOG_CIERRES_CAJA"

# Estructura exacta de tu Excel de Cierres
HEADERS_CIERRE = [
    "Fecha_Cierre", "Hora_Cierre", "Saldo_Teorico_E", "Saldo_Real_Cor", 
    "Diferencia", "Total_Nequi", "Total_Tarjetas", "Ticket_Ini", "Ticket_Fin",
    "Profit_Retenido", "Estado_Ahorro", "Numero_Cierre_Loyverse"
]

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

# --- BACKEND: CARGA Y CONSOLIDACIÓN ---

def cargar_tickets_para_cierre(sheet):
    """Lee las ventas detalladas y las consolida por recibo para Tesorería."""
    try:
        ws_v = sheet.worksheet(HOJA_VENTAS)
        df_raw = leer_datos_seguro(ws_v)
        if df_raw.empty: return pd.DataFrame()

        # Limpiar datos numéricos
        df_raw["Total_Dinero"] = pd.to_numeric(df_raw["Total_Dinero"], errors='coerce').fillna(0)
        
        # --- CONSOLIDACIÓN (Agrupar productos en un solo Ticket) ---
        df_tickets = df_raw.groupby("Numero_Recibo").agg({
            "Hora": "first",
            "Fecha": "first",
            "Total_Dinero": "sum",
            "Metodo_Pago_Loyverse": "first"
        }).reset_index()
        
        # Ordenar por el más reciente (Timestamp virtual para orden)
        df_tickets["TS"] = pd.to_datetime(df_tickets["Fecha"] + " " + df_tickets["Hora"], errors='coerce')
        df_tickets = df_tickets.sort_values("TS", ascending=False).drop(columns=["TS"])
        
        return df_tickets
    except:
        return pd.DataFrame()

# --- INTERFAZ ---

def show(sheet):
    st.title("🔐 Tesorería: Cierre por Recibos")
    st.caption("Consolida los recibos de la jornada y audita los medios de pago.")
    
    if not sheet: return

    tab_cierre, tab_hist = st.tabs(["📝 PROCESAR CIERRE", "📜 HISTORIAL"])

    with tab_cierre:
        # 1. CARGAR POOL DE TICKETS
        df_pool = cargar_tickets_para_cierre(sheet)
        
        if df_pool.empty:
            st.warning("No hay ventas descargadas en el historial. Ve al módulo 'Ventas' primero.")
            return

        st.markdown("### 🎫 Rango del Turno")
        
        # Lista de opciones para el selector
        opciones = df_pool.apply(
            lambda x: f"#{x['Numero_Recibo']} | {x['Fecha']} {x['Hora']} | Total: {formato_moneda(x['Total_Dinero'])}", 
            axis=1
        ).tolist()

        c1, c2 = st.columns(2)
        with c1:
            ticket_fin = st.selectbox("ÚLTIMO ticket del turno (Cierre):", opciones, index=0)
        with c2:
            ticket_ini = st.selectbox("PRIMER ticket del turno (Apertura):", opciones, index=min(len(opciones)-1, 10))

        # Extraer IDs
        id_ini = ticket_ini.split(" | ")[0].replace("#", "")
        id_fin = ticket_fin.split(" | ")[0].replace("#", "")

        # Filtrar el rango seleccionado
        idx_start = df_pool[df_pool["Numero_Recibo"] == id_ini].index[0]
        idx_end = df_pool[df_pool["Numero_Recibo"] == id_fin].index[0]
        
        start, end = (idx_start, idx_end) if idx_start > idx_end else (idx_end, idx_start)
        df_turno = df_pool.loc[end:start].copy()

        st.success(f"✅ **Turno detectado:** {len(df_turno)} tickets seleccionados.")

        # --- 2. AUDITORÍA DE PAGOS MIXTOS ---
        with st.expander("🛠️ Auditoría y Desglose de Pagos", expanded=True):
            st.info("Ajusta los valores si un ticket se pagó con dos métodos (ej: mitad Nequi, mitad Efectivo).")
            
            # Preparar columnas reales
            df_turno["Efectivo_Real"] = df_turno.apply(lambda x: x["Total_Dinero"] if x["Metodo_Pago_Loyverse"] == "Efectivo" else 0.0, axis=1)
            df_turno["Nequi_Real"] = df_turno.apply(lambda x: x["Total_Dinero"] if "Nequi" in str(x["Metodo_Pago_Loyverse"]) else 0.0, axis=1)
            df_turno["Tarjeta_Real"] = df_turno.apply(lambda x: x["Total_Dinero"] if "Tarjeta" in str(x["Metodo_Pago_Loyverse"]) else 0.0, axis=1)
            df_turno["Suma"] = df_turno["Efectivo_Real"] + df_turno["Nequi_Real"] + df_turno["Tarjeta_Real"]

            df_ed = st.data_editor(
                df_turno[["Numero_Recibo", "Hora", "Total_Dinero", "Efectivo_Real", "Nequi_Real", "Tarjeta_Real", "Suma"]],
                column_config={
                    "Numero_Recibo": "Ticket #",
                    "Total_Dinero": st.column_config.NumberColumn("Valor Total", format="$%d", disabled=True),
                    "Efectivo_Real": st.column_config.NumberColumn("Efectivo $", format="$%d"),
                    "Nequi_Real": st.column_config.NumberColumn("Nequi $", format="$%d"),
                    "Tarjeta_Real": st.column_config.NumberColumn("Tarjeta $", format="$%d"),
                    "Suma": st.column_config.NumberColumn("Validación", format="$%d", disabled=True),
                },
                hide_index=True, use_container_width=True, key="editor_teso_sync"
            )
            
            error_v = abs(df_ed["Total_Dinero"] - df_ed["Suma"]).sum()
            if error_v > 1:
                st.error("🚨 La repartición de dinero no coincide con el total de los tickets. Por favor corrige.")

        # --- 3. CÁLCULOS FINALES ---
        v_efec = df_ed["Efectivo_Real"].sum()
        v_total = df_ed["Total_Dinero"].sum()
        v_nequi = df_ed["Nequi_Real"].sum()
        v_tarj = df_ed["Tarjeta_Real"].sum()
        
        st.markdown("---")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("VENTA TOTAL", formato_moneda(v_total))
        k2.metric("Efectivo Turno", formato_moneda(v_efec))
        k3.metric("Nequi", formato_moneda(v_nequi))
        k4.metric("Tarjetas", formato_moneda(v_tarj))

        st.markdown("---")
        st.subheader("💵 Arqueo Físico de Efectivo")
        real = st.number_input("¿Cuánto dinero físico hay en caja?", min_value=0.0, step=500.0)
        z_rep = st.text_input("Número de Z-Report / Cierre")
        
        diff = real - v_efec
        if diff == 0: st.success("✅ CAJA CUADRADA")
        elif diff > 0: st.info(f"🔵 SOBRANTE: {formato_moneda(diff)}")
        else: st.error(f"### 🔴 FALTANTE: {formato_moneda(diff)}")

        if st.button("🔒 GUARDAR CIERRE DEFINITIVO", type="primary", use_container_width=True):
            if error_v > 1:
                st.warning("Corrige los tickets descuadrados antes de guardar.")
            elif not z_rep:
                st.warning("Ingresa el número de cierre.")
            else:
                datos = {
                    "Fecha_Cierre": datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d"),
                    "Hora_Cierre": datetime.now(ZONA_HORARIA).strftime("%H:%M"),
                    "Saldo_Teorico_E": v_efec,
                    "Saldo_Real_Cor": real,
                    "Diferencia": diff,
                    "Total_Nequi": v_nequi,
                    "Total_Tarjetas": v_tarj,
                    "Ticket_Ini": id_ini,
                    "Ticket_Fin": id_fin,
                    "Profit_Retenido": v_total * 0.05,
                    "Estado_Ahorro": "Pendiente",
                    "Numero_Cierre_Loyverse": z_rep
                }
                ws_c = sheet.worksheet(HOJA_CIERRES)
                ws_c.append_row([str(datos.get(h, "")) for h in HEADERS_CIERRE])
                st.balloons(); time.sleep(1); st.rerun()

    with tab_hist:
        st.subheader("📜 Historial de Cierres")
        if st.button("🔄 ACTUALIZAR"):
            st.cache_data.clear(); st.rerun()
            
        try:
            df_h = leer_datos_seguro(sheet.worksheet(HOJA_CIERRES))
            if not df_h.empty:
                df_h = df_h.sort_values("Fecha_Cierre", ascending=False).head(20)
                # Limpiar nombres de columnas
                df_h.columns = df_h.columns.str.strip()
                # Formatear montos
                for c in ["Saldo_Teorico_E", "Saldo_Real_Cor", "Diferencia"]:
                    if c in df_h.columns:
                        df_h[c] = pd.to_numeric(df_h[c], errors='coerce').apply(formato_moneda)
                st.dataframe(df_h, use_container_width=True, hide_index=True)
            else:
                st.info("Sin historial.")
        except: pass
