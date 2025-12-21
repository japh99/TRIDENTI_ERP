import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero, generar_id

# --- CONFIGURACIÓN ---
HOJA_VENTAS = "LOG_VENTAS_LOYVERSE"
HOJA_GASTOS = "LOG_GASTOS"
HOJA_CIERRES = "LOG_CIERRES_CAJA"

HEADERS_CIERRE = [
    "Fecha", "Hora_Cierre", "Saldo_Teorico_E", "Saldo_Real_Cor", 
    "Diferencia", "Total_Nequi", "Total_Tarjetas", "Notas", 
    "Profit_Retenido", "Estado_Ahorro", "Numero_Cierre_Loyverse"
]

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

# --- FUNCIONES DE CARGA POR TICKET ---

def cargar_pool_tickets(sheet):
    """Carga los últimos 200 tickets para que el usuario elija el rango."""
    try:
        ws_v = sheet.worksheet(HOJA_VENTAS)
        df_raw = leer_datos_seguro(ws_v)
        if df_raw.empty: return pd.DataFrame()

        df_raw["Total_Dinero"] = pd.to_numeric(df_raw["Total_Dinero"], errors='coerce').fillna(0)
        
        # Agrupar por recibo para tener la lista de tickets única
        df_tickets = df_raw.groupby("Numero_Recibo").agg({
            "Hora": "first",
            "Fecha": "first",
            "Total_Dinero": "sum",
            "Metodo_Pago_Loyverse": "first"
        }).reset_index()
        
        # Ordenar por lo más reciente (usando el índice original de llegada)
        return df_tickets.iloc[::-1] 
    except:
        return pd.DataFrame()

# --- INTERFAZ ---

def show(sheet):
    st.title("🔐 Tesorería: Cierre por Recibos")
    st.caption("Selecciona el primer y último ticket de tu turno para cuadrar caja.")
    
    if not sheet: return

    tab_cierre, tab_historial = st.tabs(["📝 PROCESAR CIERRE", "📜 HISTORIAL"])

    with tab_cierre:
        # 1. CARGAR TODOS LOS TICKETS RECIENTES
        df_pool = cargar_pool_tickets(sheet)
        
        if df_pool.empty:
            st.warning("No hay ventas registradas en el historial.")
            return

        st.markdown("### 🎫 Definir Rango del Cierre")
        st.write("Selecciona los tickets que comprenden este turno:")

        # Crear etiquetas bonitas para el selector: "#3245 - 5:20 PM ($25.000)"
        opciones_tickets = df_pool.apply(
            lambda x: f"#{x['Numero_Recibo']} | {x['Fecha']} {x['Hora']} | {formato_moneda(x['Total_Dinero'])}", 
            axis=1
        ).tolist()

        c1, c2 = st.columns(2)
        with c1:
            ticket_fin = st.selectbox("ÚLTIMO ticket del turno (el más reciente):", opciones_tickets, index=0)
        with c2:
            ticket_ini = st.selectbox("PRIMER ticket del turno (con el que abriste):", opciones_tickets, index=min(len(opciones_tickets)-1, 10))

        # Obtener los números de recibo puros
        id_ini = ticket_ini.split(" | ")[0].replace("#", "")
        id_fin = ticket_fin.split(" | ")[0].replace("#", "")

        # Filtrar el DataFrame original para obtener todo lo que está en ese rango
        # Buscamos las posiciones
        idx_ini = df_pool[df_pool["Numero_Recibo"] == id_ini].index[0]
        idx_fin = df_pool[df_pool["Numero_Recibo"] == id_fin].index[0]

        # Invertir si el usuario los seleccionó al revés
        start_pos, end_pos = (idx_ini, idx_fin) if idx_ini > idx_fin else (idx_fin, idx_ini)
        
        # El pool está invertido, así que seleccionamos el rango
        df_turno = df_pool.loc[end_pos:start_pos].copy()

        st.info(f"✅ **Turno identificado:** {len(df_turno)} tickets seleccionados.")

        # --- 2. AUDITORÍA DE ESTE TURNO ---
        with st.expander("🛠️ Auditoría de Pagos Mixtos (Editar este turno)", expanded=True):
            df_turno["Efectivo_Real"] = df_turno.apply(lambda x: x["Total_Dinero"] if x["Metodo_Pago_Loyverse"] == "Efectivo" else 0.0, axis=1)
            df_turno["Nequi_Real"] = df_turno.apply(lambda x: x["Total_Dinero"] if "Nequi" in str(x["Metodo_Pago_Loyverse"]) else 0.0, axis=1)
            df_turno["Tarjeta_Real"] = df_turno.apply(lambda x: x["Total_Dinero"] if "Tarjeta" in str(x["Metodo_Pago_Loyverse"]) else 0.0, axis=1)
            df_turno["Suma_Auditada"] = df_turno["Efectivo_Real"] + df_turno["Nequi_Real"] + df_turno["Tarjeta_Real"]

            df_ed = st.data_editor(
                df_turno[["Hora", "Numero_Recibo", "Total_Dinero", "Efectivo_Real", "Nequi_Real", "Tarjeta_Real", "Suma_Auditada"]],
                column_config={
                    "Total_Dinero": st.column_config.NumberColumn("Total Ticket", format="$%d", disabled=True),
                    "Efectivo_Real": st.column_config.NumberColumn("Efectivo $", format="$%d"),
                    "Nequi_Real": st.column_config.NumberColumn("Nequi $", format="$%d"),
                    "Tarjeta_Real": st.column_config.NumberColumn("Tarjeta $", format="$%d"),
                    "Suma_Auditada": st.column_config.NumberColumn("Suma", format="$%d", disabled=True),
                },
                hide_index=True, use_container_width=True, key="editor_teso_recibos"
            )
            
            error_v = df_ed[abs(df_ed["Total_Dinero"] - df_ed["Suma_Auditada"]) > 1]
            if not error_v.empty:
                st.error("⚠️ El desglose no coincide con el total en algunos tickets.")

        # --- 3. CÁLCULOS DEL CIERRE ---
        v_total = df_ed["Total_Dinero"].sum()
        v_efec = df_ed["Efectivo_Real"].sum()
        v_nequi = df_ed["Nequi_Real"].sum()
        v_tarj = df_ed["Tarjeta_Real"].sum()
        
        # Gastos: Para los gastos, si usaremos el rango de tiempo de los tickets seleccionados
        hora_inicio_turno = df_turno["Hora"].iloc[-1]
        hora_fin_turno = df_turno["Hora"].iloc[0]
        st.write(f"⏱️ Horario detectado: {hora_inicio_turno} a {hora_fin_turno}")

        saldo_teo = v_efec # Aquí restarías gastos si los tienes en otra hoja

        st.markdown("#### 📊 Resumen del Turno")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("VENTA TOTAL", formato_moneda(v_total))
        k2.metric("Efectivo Esperado", formato_moneda(v_efec))
        k3.metric("Nequi", formato_moneda(v_nequi))
        k4.metric("Tarjetas", formato_moneda(v_tarj))

        st.markdown("---")
        st.markdown("#### 💵 Arqueo de Caja")
        real = st.number_input("¿Cuánto efectivo hay físicamente?", min_value=0.0, step=500.0)
        z_rep = st.text_input("Z-Report / Número de Cierre")
        
        diff = real - saldo_teo
        if diff == 0: st.success(f"### ✅ CORRECTO: {formato_moneda(diff)}")
        elif diff > 0: st.info(f"### 🔵 SOBRANTE: {formato_moneda(diff)}")
        else: st.error(f"### 🔴 FALTANTE: {formato_moneda(diff)}")

        if st.button("🔒 GUARDAR CIERRE DEFINITIVO", type="primary", use_container_width=True):
            if not error_v.empty: st.warning("Corrige los tickets en rojo.")
            elif not z_rep: st.warning("Escribe el número de Z-Report.")
            else:
                datos = {
                    "Fecha": datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d"),
                    "Hora_Cierre": datetime.now(ZONA_HORARIA).strftime("%H:%M"),
                    "Saldo_Teorico_E": saldo_teo,
                    "Saldo_Real_Cor": real,
                    "Diferencia": diff,
                    "Total_Nequi": v_nequi,
                    "Total_Tarjetas": v_tarj,
                    "Notas": f"Tickets: {id_ini} al {id_fin}",
                    "Profit_Retenido": v_total * 0.05,
                    "Estado_Ahorro": "Pendiente",
                    "Numero_Cierre_Loyverse": z_rep
                }
                ws_c = sheet.worksheet(HOJA_CIERRES)
                ws_c.append_row([str(datos.get(h, "")) for h in HEADERS_CIERRE])
                st.balloons(); time.sleep(1); st.rerun()

    with tab_historial:
        st.subheader("📜 Historial de Cierres")
        try:
            df_h = leer_datos_seguro(sheet.worksheet(HOJA_CIERRES))
            if not df_h.empty:
                df_h = df_h.sort_values("Fecha", ascending=False).head(15)
                cols = ["Fecha", "Numero_Cierre_Loyverse", "Saldo_Real_Cor", "Diferencia", "Notas"]
                for c in ["Saldo_Real_Cor", "Diferencia"]:
                    df_h[c] = pd.to_numeric(df_h[c], errors='coerce').apply(formato_moneda)
                st.dataframe(df_h[cols], use_container_width=True, hide_index=True)
        except: pass
