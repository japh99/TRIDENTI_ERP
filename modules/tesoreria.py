import streamlit as st
import pandas as pd
from datetime import datetime
import time
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero, generar_id

# --- CONFIGURACIÓN DE HOJAS ---
HOJA_VENTAS = "LOG_VENTAS_LOYVERSE"
HOJA_GASTOS = "LOG_PAGOS_GASTOS"
HOJA_CIERRES = "LOG_CIERRES_CAJA"

# Encabezados de la Base de Datos
HEADERS_CIERRE = [
    "Fecha", "Hora_Cierre", "Saldo_Teorico_E", "Saldo_Real_Con", 
    "Diferencia", "Total_Nequi", "Total_Tarjetas", "Notas", 
    "Profit_Retenido", "Estado_Ahorro", "Numero_Cierre_Loyverse"
]

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

# --- LÓGICA DE DATOS BASADA EN API LOYVERSE ---

def cargar_movimientos_agrupados(sheet, fecha_str):
    try:
        ws_v = sheet.worksheet(HOJA_VENTAS)
        df_raw = leer_datos_seguro(ws_v)
        
        if not df_raw.empty:
            df_raw["Fecha"] = df_raw["Fecha"].astype(str)
            # Filtrar por fecha
            df_dia = df_raw[df_raw["Fecha"] == fecha_str].copy()
            df_dia["Total_Dinero"] = pd.to_numeric(df_dia["Total_Dinero"], errors='coerce').fillna(0)
            
            # --- AGRUPACIÓN POR TICKET (Lógica de la API) ---
            # Agrupamos por recibo para tener el total real del ticket
            df_grouped = df_dia.groupby("Numero_Recibo").agg({
                "Total_Dinero": "sum",
                "Metodo_Pago_Loyverse": "first",
                "Metodo_Pago_Real_Auditado": "first",
                "Hora": "first"
            }).reset_index()
            
            return df_grouped, df_dia, ws_v
        return pd.DataFrame(), pd.DataFrame(), ws_v
    except Exception as e:
        st.error(f"Error cargando ventas: {e}")
        return None, None, None

def guardar_correccion_masiva(ws_v, df_dia_completo, df_editado):
    """
    Busca todas las filas de un ticket en el Excel y actualiza 
    el método de pago auditado en todas ellas.
    """
    try:
        # 1. Obtener todas las posiciones de la columna Numero_Recibo (Col C = 3)
        recibos_en_excel = ws_v.col_values(3)
        
        with st.spinner("Sincronizando correcciones con el servidor..."):
            for _, row in df_editado.iterrows():
                ticket = str(row["Numero_Recibo"])
                nuevo_metodo = row["Metodo_Pago_Real_Auditado"]
                metodo_pos = row["Metodo_Pago_Loyverse"]
                
                # Solo procesamos si el usuario cambió el método original
                if nuevo_metodo != metodo_pos:
                    # Encontrar todas las filas en el Excel que tienen ese número de recibo
                    indices = [i + 1 for i, x in enumerate(recibos_en_excel) if x == ticket]
                    
                    # Actualizar cada fila encontrada (Columna I = 9: Metodo_Pago_Real_Auditado)
                    for idx in indices:
                        ws_v.update_cell(idx, 9, nuevo_metodo)
        return True
    except Exception as e:
        st.error(f"Fallo al actualizar Excel: {e}")
        return False

# --- INTERFAZ ---

def show(sheet):
    st.title("🔐 Tesorería: Cierre de Caja")
    if not sheet: return

    hoy = datetime.now(ZONA_HORARIA).date()
    fecha_cierre = st.date_input("Fecha de Trabajo", value=hoy)
    fecha_str = fecha_cierre.strftime("%Y-%m-%d")

    # Verificar si ya existe cierre
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
        # PROCESAR CIERRE
        df_tickets, df_dia_full, ws_v = cargar_movimientos_agrupados(sheet, fecha_str)
        
        if df_tickets is None or df_tickets.empty:
            st.warning("No hay ventas registradas en esta fecha.")
        else:
            # 1. AUDITORÍA POR TICKET
            with st.expander("🛠️ Auditoría de Tickets (Agrupado por Recibo)", expanded=True):
                st.write("Ajusta el 'MÉTODO REAL' si el cajero se equivocó al cerrar la cuenta.")
                df_ed = st.data_editor(
                    df_tickets[["Hora", "Numero_Recibo", "Total_Dinero", "Metodo_Pago_Loyverse", "Metodo_Pago_Real_Auditado"]],
                    column_config={
                        "Total_Dinero": st.column_config.NumberColumn("Valor Total", format="$%d", disabled=True),
                        "Metodo_Pago_Real_Auditado": st.column_config.SelectboxColumn("MÉTODO REAL", options=["Efectivo", "Nequi", "Tarjeta", "Otro"], required=True),
                        "Numero_Recibo": "Ticket #"
                    },
                    hide_index=True, use_container_width=True, key="editor_tickets"
                )
                
                if st.button("💾 GUARDAR CORRECCIONES EN EXCEL"):
                    if guardar_correccion_masiva(ws_v, df_dia_full, df_ed):
                        st.success("Excel actualizado. Recargando..."); time.sleep(1); st.rerun()

            # 2. CÁLCULOS FINALES
            v_total = df_tickets["Total_Dinero"].sum()
            v_efec = df_tickets[df_tickets["Metodo_Pago_Real_Auditado"] == "Efectivo"]["Total_Dinero"].sum()
            v_nequi = df_tickets[df_tickets["Metodo_Pago_Real_Auditado"] == "Nequi"]["Total_Dinero"].sum()
            v_tarj = df_tickets[df_tickets["Metodo_Pago_Real_Auditado"] == "Tarjeta"]["Total_Dinero"].sum()
            
            # Gastos
            try:
                ws_g = sheet.worksheet(HOJA_GASTOS)
                df_g = leer_datos_seguro(ws_g)
                g_efec = df_g[(df_g["Fecha"] == fecha_str) & (df_g["Metodo_Pago"].str.contains("Efectivo", na=False))]["Monto"].astype(float).sum()
            except: g_efec = 0
            
            saldo_teo = v_efec - g_efec

            st.markdown("#### 📊 Resumen Financiero")
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("VENTA TOTAL", formato_moneda(v_total))
            k2.metric("Efectivo", formato_moneda(v_efec))
            k3.metric("Nequi", formato_moneda(v_nequi))
            k4.metric("Tarjeta", formato_moneda(v_tarj))

            st.markdown("---")
            st.markdown("#### 💵 Arqueo de Efectivo")
            a1, a2, a3 = st.columns(3)
            a1.metric("(+) Entradas", formato_moneda(v_efec))
            a2.metric("(-) Gastos", formato_moneda(g_efec))
            a3.metric("(=) DEBE HABER", formato_moneda(saldo_teo))

            c_real, c_z = st.columns(2)
            real = c_real.number_input("Efectivo Físico Contado:", min_value=0.0, step=500.0)
            z_rep = c_z.text_input("Z-Report / Numero Cierre")
            
            diff = real - saldo_teo
            if diff == 0: st.success(f"✅ CORRECTO: {formato_moneda(diff)}")
            elif diff > 0: st.info(f"### 🔵 SOBRANTE: {formato_moneda(diff)}")
            else: st.error(f"### 🔴 FALTANTE: {formato_moneda(diff)}")

            if st.button("🔒 GUARDAR CIERRE DEFINITIVO", type="primary", use_container_width=True):
                datos = {
                    "Fecha": fecha_str, "Hora_Cierre": datetime.now(ZONA_HORARIA).strftime("%H:%M"),
                    "Saldo_Teorico_E": saldo_teo, "Saldo_Real_Con": real, "Diferencia": diff,
                    "Total_Nequi": v_nequi, "Total_Tarjetas": v_tarj, "Notas": "",
                    "Profit_Retenido": v_total * 0.05, "Estado_Ahorro": "Pendiente", "Numero_Cierre_Loyverse": z_rep
                }
                ws_c.append_row([str(datos.get(h, "")) for h in HEADERS_CIERRE])
                st.balloons(); st.rerun()
