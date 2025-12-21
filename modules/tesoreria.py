import streamlit as st
import pandas as pd
from datetime import datetime, date
import time
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero, generar_id

# --- CONFIGURACIÓN ---
HOJA_VENTAS = "LOG_VENTAS_LOYVERSE"
HOJA_GASTOS = "LOG_GASTOS"
HOJA_COMPRAS = "LOG_COMPRAS"
HOJA_CIERRES = "LOG_CIERRES_CAJA"

HEADERS_CIERRE = [
    "ID_Cierre", "Fecha", "Hora_Cierre", "Venta_Total", "Efectivo_Teorico", 
    "Efectivo_Real", "Diferencia", "Nequi_Total", "Tarjetas_Total", 
    "Gastos_Efectivo", "Profit_Sugerido", "Notas", "Z_Report"
]

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

# --- FUNCIONES ---
def asegurar_columnas(ws):
    try:
        curr = ws.row_values(1)
        if not curr: ws.append_row(HEADERS_CIERRE); return
        # Si faltan columnas, las crea
        miss = [c for c in HEADERS_CIERRE if c not in curr]
        if miss:
            nxt = len(curr) + 1
            for c in miss: ws.update_cell(1, nxt, c); nxt+=1
    except: pass

def cargar_movimientos(sheet, fecha_str):
    try:
        # Ventas
        ws_v = sheet.worksheet(HOJA_VENTAS)
        df_v = pd.DataFrame(ws_v.get_all_records())
        if not df_v.empty:
            df_v["Fecha"] = df_v["Fecha"].astype(str)
            df_v = df_v[df_v["Fecha"] == fecha_str]
            df_v["Total_Dinero"] = pd.to_numeric(df_v["Total_Dinero"], errors='coerce').fillna(0)
            df_v = df_v.drop_duplicates(subset=["Numero_Recibo", "ID_Plato", "Hora"]) # Anti-Duplicados
        
        # Gastos
        try: ws_g = sheet.worksheet(HOJA_GASTOS); df_g = leer_datos_seguro(ws_g)
        except: df_g = pd.DataFrame()
        if not df_g.empty:
            df_g["Fecha"] = df_g["Fecha"].astype(str)
            df_g = df_g[df_g["Fecha"] == fecha_str]
            df_g["Monto"] = pd.to_numeric(df_g["Monto"], errors='coerce').fillna(0)

        # Compras
        try: ws_c = sheet.worksheet(HOJA_COMPRAS); df_c = leer_datos_seguro(ws_c)
        except: df_c = pd.DataFrame()
        if not df_c.empty:
            df_c["Fecha_Registro"] = df_c["Fecha_Registro"].astype(str)
            df_c = df_c[df_c["Fecha_Registro"] == fecha_str]
            df_c["Precio_Total_Pagado"] = pd.to_numeric(df_c["Precio_Total_Pagado"], errors='coerce').fillna(0)

        return df_v, df_g, df_c, ws_v
    except: return None, None, None, None

def guardar_cierre(sheet, datos_dict):
    try:
        try: ws = sheet.worksheet(HOJA_CIERRES)
        except: ws = sheet.add_worksheet(title=HOJA_CIERRES, rows="1000", cols="20")
        
        asegurar_columnas(ws)
        
        headers = ws.row_values(1)
        row = []
        for h in headers:
            val = datos_dict.get(h, "")
            row.append(str(val)) # Guardamos todo como string para evitar errores JSON
        
        ws.append_row(row)
        return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False

def verificar_cierre(sheet, fecha):
    try:
        ws = sheet.worksheet(HOJA_CIERRES)
        df = leer_datos_seguro(ws)
        if not df.empty and "Fecha" in df.columns:
            df["Fecha"] = df["Fecha"].astype(str)
            res = df[df["Fecha"] == fecha]
            if not res.empty: return res.iloc[0]
    except: pass
    return None

def reabrir_caja(sheet, fecha):
    try:
        ws = sheet.worksheet(HOJA_CIERRES)
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        df["Fecha"] = df["Fecha"].astype(str)
        df_new = df[df["Fecha"] != fecha]
        ws.clear()
        ws.update([df_new.columns.values.tolist()] + df_new.values.tolist())
        return True
    except: return False

def actualizar_audit(sheet, df_edit):
    try:
        ws = sheet.worksheet(HOJA_VENTAS)
        col_recibos = ws.col_values(3)
        for _, row in df_edit.iterrows():
            try:
                r = str(row["Numero_Recibo"])
                idx = col_recibos.index(r) + 1
                if row["Metodo_Pago_Real_Auditado"] != row["Metodo_Pago_Loyverse"]:
                    ws.update_cell(idx, 9, row["Metodo_Pago_Real_Auditado"])
            except: pass
        return True
    except: return False

# --- UI ---
def show(sheet):
    st.title("🔐 Tesorería: Cierre de Caja")
    st.markdown("---")
    if not sheet: return

    hoy = datetime.now(ZONA_HORARIA).date()
    c1, c2 = st.columns([1, 2])
    fecha_cierre = c1.date_input("Fecha", value=hoy)
    fecha_str = fecha_cierre.strftime("%Y-%m-%d")

    # VERIFICAR SI YA ESTÁ CERRADO
    cierre_previo = verificar_cierre(sheet, fecha_str)

    if cierre_previo is not None:
        # VISTA DE LECTURA
        z = cierre_previo.get("Numero_Cierre_Loyverse", "S/N")
        st.success(f"✅ **DÍA CERRADO** (Z-Report: {z})")
        
        v_tot = float(limpiar_numero(cierre_previo.get("Venta_Total", 0)))
        efec_real = float(limpiar_numero(cierre_previo.get("Efectivo_Real", 0)))
        diff = float(limpiar_numero(cierre_previo.get("Diferencia", 0)))
        prof = float(limpiar_numero(cierre_previo.get("Profit_Sugerido", 0)))
        
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Venta Total", formato_moneda(v_tot))
        k2.metric("Efectivo Contado", formato_moneda(efec_real))
        k3.metric("Diferencia", formato_moneda(diff))
        k4.metric("Profit Sugerido", formato_moneda(prof))
        
        st.text_area("Notas:", value=cierre_previo.get("Notas",""), disabled=True)
        
        if st.button("🗑️ REABRIR CAJA (Borrar)", type="secondary"):
            if reabrir_caja(sheet, fecha_str): st.rerun()
            
    else:
        # VISTA DE EDICIÓN
        df_v, df_g, df_c, ws_v = cargar_movimientos(sheet, fecha_str)
        
        if df_v is None or df_v.empty:
            st.warning("⚠️ No hay ventas descargadas para este día.")
        else:
            # 1. AUDITORÍA
            with st.expander("🛠️ Auditoría de Medios de Pago", expanded=False):
                df_aud = df_v[["Hora","Numero_Recibo","Total_Dinero","Metodo_Pago_Loyverse","Metodo_Pago_Real_Auditado"]].drop_duplicates(subset=["Numero_Recibo"])
                df_ed = st.data_editor(
                    df_aud, 
                    column_config={"Metodo_Pago_Real_Auditado": st.column_config.SelectboxColumn("MÉTODO REAL", options=["Efectivo","Nequi","Tarjeta","Otro"], required=True)},
                    hide_index=True, use_container_width=True
                )
                if st.button("💾 Guardar Correcciones"):
                    if actualizar_audit(sheet, df_ed): st.success("Listo"); time.sleep(1); st.rerun()

            # 2. CÁLCULOS
            v_total = df_v["Total_Dinero"].sum()
            v_efec = df_v[df_v["Metodo_Pago_Real_Auditado"] == "Efectivo"]["Total_Dinero"].sum()
            v_digi = df_v[df_v["Metodo_Pago_Real_Auditado"].str.contains("Nequi|Davi|Banco|Transf", case=False, na=False)]["Total_Dinero"].sum()
            v_tarj = df_v[df_v["Metodo_Pago_Real_Auditado"].isin(["Tarjeta", "Datafono"])]["Total_Dinero"].sum()
            
            g_efec = df_g[df_g["Metodo_Pago"].str.contains("Efectivo", case=False)]["Monto"].sum() if not df_g.empty else 0
            c_efec = df_c[df_c["Metodo_Pago"].str.contains("Efectivo", case=False)]["Precio_Total_Pagado"].sum() if not df_c.empty else 0
            
            saldo_teo = v_efec - g_efec - c_efec

            # 3. RESUMEN
            st.markdown("#### 📊 Resumen Financiero")
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("VENTA TOTAL", formato_moneda(v_total))
            k2.metric("Efectivo", formato_moneda(v_efec))
            k3.metric("Digital", formato_moneda(v_digi))
            k4.metric("Tarjetas", formato_moneda(v_tarj))
            
            st.markdown("---")
            
            # PROFIT (SOLO VISUAL)
            c_prof1, c_prof2 = st.columns([1, 2])
            pct_prof = c_prof1.number_input("% Profit Sugerido", value=5, min_value=1)
            monto_prof = v_total * (pct_prof/100)
            c_prof2.info(f"💡 Deberías ahorrar: **{formato_moneda(monto_prof)}**. (Ve al módulo 'Banco Profit' para registrarlo).")
            
            st.markdown("---")

            # 4. ARQUEO
            st.markdown("#### 💵 Arqueo de Efectivo")
            c1, c2, c3 = st.columns(3)
            c1.metric("(+) Entradas Efec.", formato_moneda(v_efec))
            c2.metric("(-) Salidas Efec.", formato_moneda(g_efec + c_efec))
            c3.metric("(=) DEBE HABER", formato_moneda(saldo_teo))
            
            cr, cd = st.columns(2)
            real = cr.number_input("¿Cuánto contaste?", min_value=0.0, step=500.0)
            diff = real - saldo_teo
            
            if diff == 0: st.success("✅ CUADRADO")
            else: st.error(f"🔴 DIFERENCIA: {formato_moneda(diff)}")

            cz, cn = st.columns([1, 2])
            z = cz.text_input("Z-Report")
            notas = cn.text_area("Notas")
            
            if st.button("🔒 GUARDAR CIERRE", type="primary", use_container_width=True):
                datos = {
                    "ID_Cierre": generar_id(),
                    "Fecha": fecha_str,
                    "Hora_Cierre": datetime.now(ZONA_HORARIA).strftime("%H:%M"),
                    "Venta_Total": v_total,
                    "Efectivo_Teorico": saldo_teo,
                    "Efectivo_Real": real,
                    "Diferencia": diff,
                    "Nequi_Total": v_digi,
                    "Tarjetas_Total": v_tarj,
                    "Gastos_Efectivo": g_efec + c_efec,
                    "Profit_Sugerido": monto_prof,
                    "Notas": notas,
                    "Z_Report": str(z)
                }
                if guardar_cierre(sheet, datos):
                    st.balloons()
                    st.success("Cierre guardado.")
                    time.sleep(2)
                    st.rerun()

    # --- HISTORIAL ABAJO ---
    st.markdown("---")
    st.subheader("📜 Historial de Cierres")
    try:
        ws_h = sheet.worksheet(HOJA_CIERRES)
        df_h = leer_datos_seguro(ws_h)
        if not df_h.empty:
            df_h = df_h.sort_values("Fecha", ascending=False).head(10)
            # Formatos
            for c in ["Venta_Total", "Efectivo_Real", "Diferencia"]:
                if c in df_h.columns:
                    df_h[c] = pd.to_numeric(df_h[c], errors='coerce').apply(formato_moneda)
            st.dataframe(df_h[["Fecha", "Z_Report", "Venta_Total", "Efectivo_Real", "Diferencia", "Notas"]], use_container_width=True, hide_index=True)
    except: pass
