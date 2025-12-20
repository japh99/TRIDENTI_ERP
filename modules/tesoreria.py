import streamlit as st
import pandas as pd
from datetime import datetime, date
import time
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero

# --- CONFIGURACIÓN ---
HOJA_VENTAS = "LOG_VENTAS_LOYVERSE"
HOJA_GASTOS = "LOG_GASTOS"
HOJA_COMPRAS = "LOG_COMPRAS"
HOJA_CIERRES = "LOG_CIERRES_CAJA"

# Encabezados Oficiales (V7.5)
HEADERS_CIERRE = [
    "Fecha", "Hora_Cierre", "Venta_Total_Bruta", "Venta_Efectivo", 
    "Gastos_Pagados_Efectivo", "Saldo_Teorico_Efectivo", "Saldo_Real_Contado", 
    "Diferencia", "Total_Nequi", "Total_Tarjetas", "Notas", 
    "Profit_Retenido", "Estado_Ahorro", "Numero_Cierre_Loyverse"
]

def formato_moneda_co(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

# --- FUNCIONES ---
def asegurar_columnas(ws):
    try:
        curr = ws.row_values(1)
        if not curr: ws.append_row(HEADERS_CIERRE); return
        miss = [c for c in HEADERS_CIERRE if c not in curr]
        if miss:
            nxt = len(curr) + 1
            for c in miss: ws.update_cell(1, nxt, c); nxt += 1
    except: pass

def verificar_cierre_existente(sheet, fecha_str):
    try:
        ws = sheet.worksheet(HOJA_CIERRES)
        df = leer_datos_seguro(ws)
        if not df.empty and "Fecha" in df.columns:
            df["Fecha"] = df["Fecha"].astype(str)
            row = df[df["Fecha"] == fecha_str]
            if not row.empty: return row.iloc[0]
        return None
    except: return None

def cargar_historial_completo(sheet):
    """Carga historial blindado contra columnas faltantes."""
    try:
        ws = sheet.worksheet(HOJA_CIERRES)
        df = leer_datos_seguro(ws)
        
        # BLINDAJE: Si faltan columnas nuevas en datos viejos, crearlas en memoria
        for col in HEADERS_CIERRE:
            if col not in df.columns:
                df[col] = 0 # Rellenar con 0 lo que falte
        
        return df
    except: return pd.DataFrame()

def reabrir_caja(sheet, fecha_str):
    try:
        ws = sheet.worksheet(HOJA_CIERRES)
        data = ws.get_all_records()
        if not data: return True
        df = pd.DataFrame(data)
        df["Fecha"] = df["Fecha"].astype(str)
        df_new = df[df["Fecha"] != fecha_str]
        ws.clear()
        ws.update([df_new.columns.values.tolist()] + df_new.values.tolist())
        return True
    except: return False

def cargar_movimientos(sheet, fecha_str):
    try:
        ws_v = sheet.worksheet(HOJA_VENTAS); df_v = pd.DataFrame(ws_v.get_all_records())
        if not df_v.empty:
            df_v["Fecha"] = df_v["Fecha"].astype(str)
            df_v = df_v[df_v["Fecha"] == fecha_str]
            df_v = df_v.drop_duplicates(subset=["Numero_Recibo", "ID_Plato", "Hora"])
            df_v["Total_Dinero"] = pd.to_numeric(df_v["Total_Dinero"], errors='coerce').fillna(0)
        
        try: ws_g = sheet.worksheet(HOJA_GASTOS); df_g = leer_datos_seguro(ws_g)
        except: df_g = pd.DataFrame()
        if not df_g.empty:
            df_g["Fecha"] = df_g["Fecha"].astype(str)
            df_g = df_g[df_g["Fecha"] == fecha_str]
            df_g["Monto"] = pd.to_numeric(df_g["Monto"], errors='coerce').fillna(0)

        try: ws_c = sheet.worksheet(HOJA_COMPRAS); df_c = leer_datos_seguro(ws_c)
        except: df_c = pd.DataFrame()
        if not df_c.empty:
            df_c["Fecha_Registro"] = df_c["Fecha_Registro"].astype(str)
            df_c = df_c[df_c["Fecha_Registro"] == fecha_str]
            df_c["Precio_Total_Pagado"] = pd.to_numeric(df_c["Precio_Total_Pagado"], errors='coerce').fillna(0)

        return df_v, df_g, df_c
    except: return None, None, None

def actualizar_metodos_pago(ws_ventas, df_editado):
    try:
        col_recibos = ws_ventas.col_values(3)
        for index, row in df_editado.iterrows():
            recibo = str(row["Numero_Recibo"])
            nuevo = row["Metodo_Pago_Real_Auditado"]
            orig = row["Metodo_Pago_Loyverse"]
            if nuevo != orig:
                try:
                    fila = col_recibos.index(recibo) + 1 
                    ws_ventas.update_cell(fila, 9, nuevo)
                except: pass
        return True
    except: return False

def guardar_cierre(sheet, datos):
    try:
        try: ws = sheet.worksheet(HOJA_CIERRES)
        except: ws = sheet.add_worksheet(title=HOJA_CIERRES, rows="1000", cols="15")
        
        asegurar_columnas(ws)
        
        headers = ws.row_values(1)
        row = []
        for h in headers:
            val = datos.get(h, "")
            row.append(float(val) if isinstance(val, (int, float)) else str(val))
        ws.append_row(row)
        return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False

# --- INTERFAZ ---
def show(sheet):
    st.title("🔐 Tesorería: Cierre de Caja")
    st.caption("Cuadre diario y registro histórico.")
    st.markdown("---")
    
    if not sheet: return

    tab1, tab2 = st.tabs(["📝 CIERRE DEL DÍA", "📜 HISTORIAL DE CIERRES"])

    # TAB 1
    with tab1:
        hoy = datetime.now(ZONA_HORARIA).date()
        col_f, col_s = st.columns([1, 2])
        fecha_cierre = col_f.date_input("Fecha", value=hoy)
        fecha_str = fecha_cierre.strftime("%Y-%m-%d")

        datos_cierre = verificar_cierre_existente(sheet, fecha_str)

        if datos_cierre is not None:
            z = datos_cierre.get("Numero_Cierre_Loyverse", "S/N")
            with col_s: st.success(f"✅ **DÍA CERRADO** (Z: {z})")
            
            # Recuperar datos con blindaje
            teorico = float(limpiar_numero(datos_cierre.get("Saldo_Teorico_Efectivo", 0)))
            real = float(limpiar_numero(datos_cierre.get("Saldo_Real_Contado", 0)))
            diff = float(limpiar_numero(datos_cierre.get("Diferencia", 0)))
            profit = float(limpiar_numero(datos_cierre.get("Profit_Retenido", 0)))
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Debía Haber", formato_moneda_co(teorico))
            c2.metric("Se Contó", formato_moneda_co(real))
            c3.metric("Diferencia", formato_moneda_co(diff), delta_color="off")
            
            st.info(f"🐷 Ahorro: **{formato_moneda_co(profit)}** ({datos_cierre.get('Estado_Ahorro','-')})")
            st.text_area("Notas:", value=datos_cierre.get("Notas", ""), disabled=True)
            
            if st.button("🗑️ REABRIR CAJA", type="secondary"):
                if reabrir_caja(sheet, fecha_str): st.success("Reabierto."); time.sleep(1); st.rerun()

        else:
            with col_s: st.warning("⚠️ **PENDIENTE**")
            df_ventas, df_g, df_c = cargar_movimientos(sheet, fecha_str)

            v_total=0; v_ef=0; v_dig=0; v_tar=0; g_ef=0; c_ef=0
            if df_ventas is not None and not df_ventas.empty:
                # Auditoría
                with st.expander("🛠️ Auditoría Pagos", expanded=False):
                    df_aud = df_ventas[["Hora","Numero_Recibo","Total_Dinero","Metodo_Pago_Loyverse","Metodo_Pago_Real_Auditado"]].drop_duplicates(subset=["Numero_Recibo"])
                    df_ed = st.data_editor(df_aud, column_config={"Metodo_Pago_Real_Auditado": st.column_config.SelectboxColumn("MÉTODO REAL", options=["Efectivo","Nequi","Tarjeta","Otro"], required=True)}, hide_index=True, use_container_width=True)
                    if st.button("💾 Guardar Correcciones"):
                        ws_v = sheet.worksheet(HOJA_VENTAS)
                        if actualizar_metodos_pago(ws_v, df_ed): st.success("Listo."); st.rerun()

                v_total = df_ventas["Total_Dinero"].sum()
                v_ef = df_ventas[df_ventas["Metodo_Pago_Real_Auditado"]=="Efectivo"]["Total_Dinero"].sum()
                v_dig = df_ventas[df_ventas["Metodo_Pago_Real_Auditado"].str.contains("Nequi|Davi|Banco", case=False)]["Total_Dinero"].sum()
                v_tar = df_ventas[df_ventas["Metodo_Pago_Real_Auditado"].isin(["Tarjeta","Datafono"])]["Total_Dinero"].sum()
                
                g_ef = df_g[df_g["Metodo_Pago"].str.contains("Efectivo", case=False)]["Monto"].sum() if not df_g.empty else 0
                c_ef = df_c[df_c["Metodo_Pago"].str.contains("Efectivo", case=False)]["Precio_Total_Pagado"].sum() if not df_c.empty else 0

            saldo_teo = v_ef - g_ef - c_ef

            st.markdown("#### Resumen Financiero")
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("VENTA TOTAL", formato_moneda_co(v_total))
            k2.metric("Efectivo", formato_moneda_co(v_ef))
            k3.metric("Digital", formato_moneda_co(v_dig))
            k4.metric("Tarjetas", formato_moneda_co(v_tar))
            
            st.markdown("---")
            st.subheader("💰 Fondo de Ahorro")
            c_p1, c_p2 = st.columns([1, 2])
            pct_prof = c_p1.number_input("% Ahorro", value=5, min_value=0)
            sugerido = v_total * (pct_prof/100)
            
            with c_p2:
                st.caption(f"Sugerido: {formato_moneda_co(sugerido)}")
                monto_real = st.number_input("💵 Ahorrar Hoy (Editable)", value=float(sugerido), step=1000.0)
                estado_ah = st.radio("Estado:", ["🔴 PENDIENTE", "🟢 GUARDADO"], horizontal=True)

            st.markdown("---")
            st.subheader("💵 Arqueo de Efectivo")
            c1, c2, c3 = st.columns(3)
            c1.metric("(+) Entradas", formato_moneda_co(v_ef))
            c2.metric("(-) Salidas", formato_moneda_co(g_ef + c_ef))
            c3.metric("(=) TEÓRICO", formato_moneda_co(saldo_teo))
            
            col_r, col_d = st.columns(2)
            real = col_r.number_input("¿Cuánto contaste?", min_value=0.0, step=500.0)
            diff = real - saldo_teo
            
            with col_d:
                if diff == 0: st.success("✅ CUADRADO")
                else: st.error(f"🔴 FALTA: {formato_moneda_co(diff)}") if diff < 0 else st.info(f"🔵 SOBRA: {formato_moneda_co(diff)}")

            c_z, c_n = st.columns([1, 2])
            z = c_z.text_input("Z-Report")
            notas = c_n.text_area("Notas")
            
            if st.button("🔒 CERRAR CAJA", type="primary", use_container_width=True):
                est = "GUARDADO" if "🟢" in estado_ah else "PENDIENTE"
                if monto_real == 0: est = "N/A"
                d = {
                    "Fecha": fecha_str, "Hora_Cierre": datetime.now(ZONA_HORARIA).strftime("%H:%M"),
                    "Venta_Total_Bruta": v_total, "Venta_Efectivo": v_ef, "Gastos_Pagados_Efectivo": g_ef+c_ef,
                    "Saldo_Teorico_Efectivo": saldo_teo, "Saldo_Real_Contado": real, "Diferencia": diff,
                    "Total_Nequi": v_dig, "Total_Tarjetas": v_tar, "Notas": notas,
                    "Profit_Retenido": monto_real, "Estado_Ahorro": est, "Numero_Cierre_Loyverse": str(z)
                }
                if guardar_cierre(sheet, d):
                    st.balloons(); st.success("Guardado."); time.sleep(2); st.rerun()

    # TAB 2: HISTORIAL
    with tab2:
        st.subheader("📜 Historial de Cierres")
        df_full = cargar_historial_completo(sheet)
        if not df_full.empty:
            df_ver = df_full.copy()
            # Formatos visuales
            for col in ["Venta_Total_Bruta", "Saldo_Real_Contado", "Diferencia", "Profit_Retenido"]:
                if col in df_ver.columns:
                    df_ver[col] = pd.to_numeric(df_ver[col], errors='coerce').apply(formato_moneda_co)
            
            st.dataframe(
                df_ver[["Fecha", "Numero_Cierre_Loyverse", "Venta_Total_Bruta", "Saldo_Real_Contado", "Diferencia", "Profit_Retenido", "Notas"]].sort_values("Fecha", ascending=False),
                use_container_width=True, hide_index=True
            )
        else: st.info("Sin historial.")
