import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dt_time
import time
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero, generar_id

# --- CONFIGURACIÓN ---
HOJA_VENTAS = "LOG_VENTAS_LOYVERSE"
HOJA_GASTOS = "LOG_GASTOS"
HOJA_CIERRES = "LOG_CIERRES_CAJA"

# Estructura de base de datos exacta
HEADERS_CIERRE = [
    "Fecha_Cierre", "Hora_Cierre", "Saldo_Teorico_E", "Saldo_Real_Cor", 
    "Diferencia", "Total_Nequi", "Total_Tarjetas", "Ticket_Ini", "Ticket_Fin",
    "Profit_Retenido", "Estado_Ahorro", "Numero_Cierre_Loyverse"
]

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

# --- BACKEND: CARGA POR TICKETS ---

def cargar_pool_tickets(sheet):
    """Carga los últimos tickets para que el usuario elija el rango del turno."""
    try:
        ws_v = sheet.worksheet(HOJA_VENTAS)
        df_raw = leer_datos_seguro(ws_v)
        if df_raw.empty: return pd.DataFrame()

        df_raw["Total_Dinero"] = pd.to_numeric(df_raw["Total_Dinero"], errors='coerce').fillna(0)
        
        # Agrupamos por recibo para tener la lista de tickets única
        df_tickets = df_raw.groupby("Numero_Recibo").agg({
            "Hora": "first",
            "Fecha": "first",
            "Total_Dinero": "sum",
            "Metodo_Pago_Loyverse": "first"
        }).reset_index()
        
        # Devolver en orden inverso para que los más nuevos salgan arriba
        return df_tickets.iloc[::-1] 
    except:
        return pd.DataFrame()

# --- INTERFAZ ---

def show(sheet):
    st.title("🔐 Tesorería: Cierre por Recibos")
    st.caption("Selecciona el ticket de inicio y fin para procesar el cierre del turno.")
    
    if not sheet: return

    tab_cierre, tab_hist = st.tabs(["📝 PROCESAR CIERRE", "📜 HISTORIAL"])

    with tab_cierre:
        # 1. CARGAR TICKETS
        df_pool = cargar_pool_tickets(sheet)
        
        if df_pool.empty:
            st.warning("No hay ventas registradas en el historial de Loyverse.")
            return

        st.markdown("### 🎫 Definir Rango del Cierre")
        
        # Crear etiquetas para el selectbox
        opciones_tickets = df_pool.apply(
            lambda x: f"#{x['Numero_Recibo']} | {x['Fecha']} {x['Hora']} | {formato_moneda(x['Total_Dinero'])}", 
            axis=1
        ).tolist()

        c1, c2 = st.columns(2)
        with c1:
            ticket_fin = st.selectbox("ÚLTIMO ticket del turno (Cierre):", opciones_tickets, index=0)
        with c2:
            ticket_ini = st.selectbox("PRIMER ticket del turno (Apertura):", opciones_tickets, index=min(len(opciones_tickets)-1, 15))

        # Obtener los IDs limpios
        id_ini = ticket_ini.split(" | ")[0].replace("#", "")
        id_fin = ticket_fin.split(" | ")[0].replace("#", "")

        # Obtener posiciones en el DataFrame
        idx_start = df_pool[df_pool["Numero_Recibo"] == id_ini].index[0]
        idx_end = df_pool[df_pool["Numero_Recibo"] == id_fin].index[0]

        # Invertir si es necesario
        start, end = (idx_start, idx_end) if idx_start > idx_end else (idx_end, idx_start)
        df_turno = df_pool.loc[end:start].copy()

        st.success(f"✅ **Turno detectado:** {len(df_turno)} tickets seleccionados.")

        # --- 2. AUDITORÍA DE PAGOS MIXTOS ---
        with st.expander("🛠️ Auditoría de Pagos Mixtos (Corregir este turno)", expanded=True):
            df_turno["Efectivo_Real"] = df_turno.apply(lambda x: x["Total_Dinero"] if x["Metodo_Pago_Loyverse"] == "Efectivo" else 0.0, axis=1)
            df_turno["Nequi_Real"] = df_turno.apply(lambda x: x["Total_Dinero"] if "Nequi" in str(x["Metodo_Pago_Loyverse"]) else 0.0, axis=1)
            df_turno["Tarjeta_Real"] = df_turno.apply(lambda x: x["Total_Dinero"] if "Tarjeta" in str(x["Metodo_Pago_Loyverse"]) else 0.0, axis=1)
            df_turno["Suma"] = df_turno["Efectivo_Real"] + df_turno["Nequi_Real"] + df_turno["Tarjeta_Real"]

            df_ed = st.data_editor(
                df_turno[["Numero_Recibo", "Hora", "Total_Dinero", "Efectivo_Real", "Nequi_Real", "Tarjeta_Real", "Suma"]],
                column_config={
                    "Total_Dinero": st.column_config.NumberColumn("Total", format="$%d", disabled=True),
                    "Efectivo_Real": st.column_config.NumberColumn("Efectivo $", format="$%d"),
                    "Nequi_Real": st.column_config.NumberColumn("Nequi $", format="$%d"),
                    "Tarjeta_Real": st.column_config.NumberColumn("Tarjeta $", format="$%d"),
                    "Suma": st.column_config.NumberColumn("Validación", format="$%d", disabled=True),
                },
                hide_index=True, use_container_width=True, key="editor_teso_fix"
            )
            
            dif_check = abs(df_ed["Total_Dinero"] - df_ed["Suma"]).sum()
            if dif_check > 1:
                st.error("🚨 La repartición de dinero no coincide con el total de los tickets.")

        # --- 3. CÁLCULOS Y ARQUEO ---
        v_efec = df_ed["Efectivo_Real"].sum()
        v_total = df_ed["Total_Dinero"].sum()
        v_digital = df_ed["Nequi_Real"].sum() + df_ed["Tarjeta_Real"].sum()

        st.markdown("---")
        m1, m2, m3 = st.columns(3)
        m1.metric("Efectivo a Entregar", formato_moneda(v_efec))
        m2.metric("Venta Bruta Turno", formato_moneda(v_total))
        m3.metric("Digital / Tarjetas", formato_moneda(v_digital))

        col_arqueo, col_z = st.columns(2) # VARIABLE CORREGIDA AQUÍ (col_arqueo)
        real = col_arqueo.number_input("¿Cuánto efectivo hay físicamente?", min_value=0.0, step=500.0)
        z_rep = col_z.text_input("Z-Report / Número Cierre")
        
        diff = real - v_efec
        if diff == 0: st.success("✅ CAJA CUADRADA")
        elif diff > 0: st.info(f"🔵 SOBRANTE: {formato_moneda(diff)}")
        else: st.error(f"### 🔴 FALTANTE: {formato_moneda(diff)}")

        if st.button("🔒 GUARDAR CIERRE DEFINITIVO", type="primary", use_container_width=True):
            if dif_check > 1:
                st.warning("Corrige el desglose de los tickets en rojo.")
            elif not z_rep:
                st.warning("Ingresa el número de Z-Report.")
            else:
                datos = {
                    "Fecha_Cierre": datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d"),
                    "Hora_Cierre": datetime.now(ZONA_HORARIA).strftime("%H:%M"),
                    "Saldo_Teorico_E": v_efec,
                    "Saldo_Real_Cor": real,
                    "Diferencia": diff,
                    "Total_Nequi": df_ed["Nequi_Real"].sum(),
                    "Total_Tarjetas": df_ed["Tarjeta_Real"].sum(),
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
        
        # BOTÓN ESPECIAL PARA LIMPIAR CACHÉ (Ya que el menú está oculto)
        if st.button("🔄 ACTUALIZAR DATOS (Limpiar Memoria)"):
            st.cache_data.clear()
            st.rerun()
            
        try:
            ws_h = sheet.worksheet(HOJA_CIERRES)
            df_h = leer_datos_seguro(ws_h)
            if not df_h.empty:
                df_h = df_h.sort_values("Fecha_Cierre", ascending=False).head(20)
                # Formatear montos para la tabla
                for c in ["Saldo_Teorico_E", "Saldo_Real_Cor", "Diferencia"]:
                    if c in df_h.columns:
                        df_h[c] = pd.to_numeric(df_h[c], errors='coerce').apply(formato_moneda)
                st.dataframe(df_h, use_container_width=True, hide_index=True)
            else:
                st.info("Sin cierres registrados.")
        except:
            st.write("Cargando historial...")
