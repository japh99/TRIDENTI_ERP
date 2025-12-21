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

# Encabezados Oficiales
HEADERS_CIERRE = [
    "Fecha", "Hora_Cierre", "Venta_Total_Bruta", "Venta_Efectivo", 
    "Gastos_Pagados_Efectivo", "Saldo_Teorico_Efectivo", "Saldo_Real_Contado", 
    "Diferencia", "Total_Nequi", "Total_Tarjetas", "Notas", 
    "Profit_Sugerido", "Numero_Cierre_Loyverse"
]

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

# --- FUNCIONES DE BASE DE DATOS ---

def asegurar_columnas(ws):
    try:
        curr = ws.row_values(1)
        if not curr:
            ws.append_row(HEADERS_CIERRE)
            return
        
        miss = [c for c in HEADERS_CIERRE if c not in curr]
        if miss:
            nxt = len(curr) + 1
            for c in miss: ws.update_cell(1, nxt, c); nxt+=1
    except: pass

def verificar_cierre(sheet, fecha):
    try:
        ws = sheet.worksheet(HOJA_CIERRES)
        df = leer_datos_seguro(ws)
        if not df.empty and "Fecha" in df.columns:
            df["Fecha"] = df["Fecha"].astype(str)
            row = df[df["Fecha"] == fecha]
            if not row.empty: return row.iloc[0]
    except: pass
    return None

def reabrir_caja(sheet, fecha):
    try:
        ws = sheet.worksheet(HOJA_CIERRES)
        data = ws.get_all_records()
        if not data: return True
        df = pd.DataFrame(data)
        df["Fecha"] = df["Fecha"].astype(str)
        df_new = df[df["Fecha"] != fecha]
        ws.clear()
        ws.update([df_new.columns.values.tolist()] + df_new.values.tolist())
        return True
    except: return False

def cargar_movimientos(sheet, fecha):
    try:
        # Ventas (Con limpieza de duplicados)
        ws_v = sheet.worksheet(HOJA_VENTAS)
        df_v = pd.DataFrame(ws_v.get_all_records())
        if not df_v.empty:
            df_v["Fecha"] = df_v["Fecha"].astype(str)
            df_v = df_v[df_v["Fecha"] == fecha]
            df_v = df_v.drop_duplicates(subset=["Numero_Recibo", "ID_Plato", "Hora"])
            df_v["Total_Dinero"] = pd.to_numeric(df_v["Total_Dinero"], errors='coerce').fillna(0)
        
        # Gastos
        try: ws_g = sheet.worksheet(HOJA_GASTOS); df_g = leer_datos_seguro(ws_g)
        except: df_g = pd.DataFrame()
        if not df_g.empty:
            df_g["Fecha"] = df_g["Fecha"].astype(str)
            df_g = df_g[df_g["Fecha"] == fecha]
            df_g["Monto"] = pd.to_numeric(df_g["Monto"], errors='coerce').fillna(0)

        # Compras
        try: ws_c = sheet.worksheet(HOJA_COMPRAS); df_c = leer_datos_seguro(ws_c)
        except: df_c = pd.DataFrame()
        if not df_c.empty:
            df_c["Fecha_Registro"] = df_c["Fecha_Registro"].astype(str)
            df_c = df_c[df_c["Fecha_Registro"] == fecha]
            df_c["Precio_Total_Pagado"] = pd.to_numeric(df_c["Precio_Total_Pagado"], errors='coerce').fillna(0)

        return df_v, df_g, df_c, ws_v
    except: return None, None, None, None

def actualizar_audit(sheet, df_edit):
    try:
        ws = sheet.worksheet(HOJA_VENTAS)
        col_recibos = ws.col_values(3)
        for _, row in df_edit.iterrows():
            try:
                r = str(row["Numero_Recibo"])
                if r in col_recibos:
                    idx = col_recibos.index(r) + 1
                    if row["Metodo_Pago_Real_Auditado"] != row["Metodo_Pago_Loyverse"]:
                        ws.update_cell(idx, 9, row["Metodo_Pago_Real_Auditado"])
            except: pass
        return True
    except: return False

def guardar_cierre(sheet, datos_dict):
    try:
        try: ws = sheet.worksheet(HOJA_CIERRES)
        except: ws = sheet.add_worksheet(title=HOJA_CIERRES, rows="1000", cols="20")
        
        asegurar_columnas(ws)
        
        headers = ws.row_values(1)
        row = []
        for h in headers:
            val = datos_dict.get(h, "")
            row.append(float(val) if isinstance(val, (int, float)) else str(val))
        
        ws.append_row(row)
        return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False

# --- INTERFAZ ---
def show(sheet):
    st.title("🔐 Tesorería: Cierre de Caja")
    st.caption("Cuadre de efectivo diario.")
    st.markdown("---")
    
    if not sheet: return

    # PESTAÑAS (Aquí separamos Historial de la Acción)
    tab_accion, tab_historial = st.tabs(["📝 CIERRE DEL DÍA", "📜 HISTORIAL ORDENADO"])

    with tab_accion:
        hoy = datetime.now(ZONA_HORARIA).date()
        col1, col2 = st.columns([1, 2])
        fecha_cierre = col1.date_input("Fecha", value=hoy)
        fecha_str = fecha_cierre.strftime("%Y-%m-%d")

        # Verificar Estado
        cierre_previo = verificar_cierre(sheet, fecha_str)

        # === MODO LECTURA (YA CERRADO) ===
        if cierre_previo is not None:
            z = cierre_previo.get("Numero_Cierre_Loyverse", "S/N")
            with col2: st.success(f"✅ **DÍA CERRADO** (Z-Report: {z})")
            
            # Recuperar datos
            teorico = float(limpiar_numero(cierre_previo.get("Saldo_Teorico_Efectivo", 0)))
            real = float(limpiar_numero(cierre_previo.get("Saldo_Real_Contado", 0)))
            diff = float(limpiar_numero(cierre_previo.get("Diferencia", 0)))
            profit = float(limpiar_numero(cierre_previo.get("Profit_Sugerido", 0)))
            
            # Tarjetas
            k1, k2, k3 = st.columns(3)
            k1.metric("Debía Haber", formato_moneda(teorico))
            k2.metric("Se Contó", formato_moneda(real))
            
            # Semáforo Diferencia en Lectura
            if diff == 0:
                k3.success(f"✅ Cuadrado ($0)")
            elif diff > 0:
                k3.info(f"🔵 Sobrante: {formato_moneda(diff)}")
            else:
                k3.error(f"🔴 Faltante: {formato_moneda(diff)}")

            st.caption(f"Sugerencia de Ahorro generada ese día: {formato_moneda(profit)}")
            st.text_area("Notas:", value=cierre_previo.get("Notas", ""), disabled=True)
            
            if st.button("🗑️ REABRIR CAJA (Corregir)", type="secondary"):
                if reabrir_caja(sheet, fecha_str): st.rerun()

        # === MODO EDICIÓN (ABIERTO) ===
        else:
            df_v, df_g, df_c, ws_v = cargar_movimientos(sheet, fecha_str)

            if df_v is None or df_v.empty:
                st.warning("⚠️ No hay ventas descargadas para hoy.")
            else:
                # 1. Auditoría
                with st.expander("🛠️ Auditoría de Medios de Pago", expanded=False):
                    df_aud = df_v[["Hora","Numero_Recibo","Total_Dinero","Metodo_Pago_Loyverse","Metodo_Pago_Real_Auditado"]].drop_duplicates(subset=["Numero_Recibo"])
                    df_ed = st.data_editor(df_aud, column_config={"Metodo_Pago_Real_Auditado": st.column_config.SelectboxColumn("MÉTODO REAL", options=["Efectivo","Nequi","Tarjeta","Otro"], required=True)}, hide_index=True, use_container_width=True)
                    if st.button("💾 Guardar Correcciones"):
                        if actualizar_audit(sheet, df_ed): st.success("Listo"); time.sleep(1); st.rerun()

                # 2. Cálculos
                v_tot = df_v["Total_Dinero"].sum()
                v_efec = df_v[df_v["Metodo_Pago_Real_Auditado"]=="Efectivo"]["Total_Dinero"].sum()
                v_digi = df_v[df_v["Metodo_Pago_Real_Auditado"].str.contains("Nequi|Davi|Banco", case=False)]["Total_Dinero"].sum()
                v_tarj = df_v[df_v["Metodo_Pago_Real_Auditado"].isin(["Tarjeta","Datafono"])]["Total_Dinero"].sum()
                
                g_efec = df_g[df_g["Metodo_Pago"].str.contains("Efectivo", case=False)]["Monto"].sum() if not df_g.empty else 0
                c_efec = df_c[df_c["Metodo_Pago"].str.contains("Efectivo", case=False)]["Precio_Total_Pagado"].sum() if not df_c.empty else 0
                
                saldo_teo = v_efec - g_efec - c_efec

                # 3. Resumen
                st.write("#### 📊 Resumen Financiero")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("VENTA TOTAL", formato_moneda(v_tot))
                c2.metric("Efectivo", formato_moneda(v_efec))
                c3.metric("Digital", formato_moneda(v_digi))
                c4.metric("Tarjetas", formato_moneda(v_tarj))
                
                st.markdown("---")
                
                # 4. Profit First (Solo sugerencia)
                cp1, cp2 = st.columns([1, 2])
                pct_prof = cp1.number_input("% Ahorro", value=5, min_value=0)
                monto_prof = v_tot * (pct_prof/100)
                cp2.info(f"💡 Sugerencia Profit: **{formato_moneda(monto_prof)}**. (Gestionar en módulo 'Banco Profit').")
                
                st.markdown("---")
                
                # 5. Arqueo
                st.write("#### 💵 Conteo de Billetes")
                k1, k2, k3 = st.columns(3)
                k1.metric("(+) Entradas", formato_moneda(v_efec))
                k2.metric("(-) Salidas", formato_moneda(g_efec + c_efec))
                k3.metric("(=) TEÓRICO", formato_moneda(saldo_teo))
                
                real = st.number_input("¿Cuánto contaste?", min_value=0.0, step=500.0)
                diff = real - saldo_teo
                
                # SEMÁFORO DE DIFERENCIA VISUAL
                if diff == 0:
                    st.success("✅ **CUADRE PERFECTO**")
                elif diff > 0:
                    st.info(f"🔵 **SOBRANTE:** {formato_moneda(diff)}")
                else:
                    st.error(f"🔴 **FALTANTE:** {formato_moneda(diff)}")
                
                z_rep = st.text_input("🧾 Z-Report (Loyverse)", placeholder="#1050")
                notas = st.text_area("Notas del Cierre")
                
                if st.button("🔒 GUARDAR CIERRE", type="primary", use_container_width=True):
                    d = {
                        "Fecha": fecha_str, "Hora_Cierre": datetime.now(ZONA_HORARIA).strftime("%H:%M"),
                        "Venta_Total_Bruta": v_tot, "Venta_Efectivo": v_efec,
                        "Gastos_Pagados_Efectivo": g_efec+c_efec, "Saldo_Teorico_Efectivo": saldo_teo,
                        "Saldo_Real_Contado": real, "Diferencia": diff,
                        "Total_Nequi": v_digi, "Total_Tarjetas": v_tarj,
                        "Notas": notas, "Profit_Sugerido": monto_prof, "Numero_Cierre_Loyverse": str(z_rep)
                    }
                    if guardar_cierre(sheet, d):
                        st.balloons(); st.success("Guardado."); time.sleep(2); st.rerun()

    # ==========================
    # PESTAÑA 2: HISTORIAL
    # ==========================
    with tab_historial:
        st.subheader("📜 Bitácora de Cierres")
        
        try:
            ws_h = sheet.worksheet(HOJA_CIERRES)
            df_h = leer_datos_seguro(ws_h)
            
            if not df_h.empty:
                # Ordenar
                df_h = df_h.sort_values("Fecha", ascending=False)
                
                # Crear Tabla Visual Bonita
                df_view = pd.DataFrame()
                df_view["Fecha"] = df_h["Fecha"]
                df_view["Z-Report"] = df_h["Numero_Cierre_Loyverse"]
                
                # Formatear dineros
                df_view["Venta Total"] = pd.to_numeric(df_h["Venta_Total_Bruta"], errors='coerce').apply(formato_moneda)
                df_view["En Cajón"] = pd.to_numeric(df_h["Saldo_Real_Contado"], errors='coerce').apply(formato_moneda)
                
                # Columna Estado (Cuadre)
                def get_status(diff):
                    d = float(limpiar_numero(diff))
                    if d == 0: return "✅ OK"
                    elif d > 0: return f"🔵 +{formato_moneda(d)}"
                    else: return f"🔴 {formato_moneda(d)}"
                
                df_view["Estado Caja"] = df_h["Diferencia"].apply(get_status)
                df_view["Notas"] = df_h["Notas"]
                
                st.dataframe(
                    df_view,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Notas": st.column_config.TextColumn("Observaciones", width="large"),
                        "Estado Caja": st.column_config.TextColumn("Cuadre", width="medium"),
                    }
                )
            else:
                st.info("No hay historial disponible.")
        except:
            st.info("Aún no se ha creado la hoja de cierres.")
