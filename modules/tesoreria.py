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

def formato_moneda_co(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

# --- FUNCIONES ---
def verificar_cierre_existente(sheet, fecha_str):
    try:
        ws = sheet.worksheet(HOJA_CIERRES)
        df = leer_datos_seguro(ws)
        if not df.empty and "Fecha" in df.columns:
            df["Fecha"] = df["Fecha"].astype(str)
            cierre = df[df["Fecha"] == fecha_str]
            if not cierre.empty: return cierre.iloc[0]
        return None
    except: return None

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
            
        return df_v, df_g, df_c, ws_v
    except: return None, None, None, None

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
        
        # Headers fijos para evitar errores
        HEADS = ["Fecha", "Hora_Cierre", "Venta_Total_Bruta", "Venta_Efectivo", 
                 "Gastos_Pagados_Efectivo", "Saldo_Teorico_Efectivo", "Saldo_Real_Contado", 
                 "Diferencia", "Total_Nequi", "Total_Tarjetas", "Notas", 
                 "Profit_Retenido", "Estado_Ahorro", "Numero_Cierre_Loyverse"]
        
        curr = ws.row_values(1)
        if not curr: ws.append_row(HEADS)
        else:
            miss = [c for c in HEADS if c not in curr]
            if miss:
                nxt = len(curr) + 1
                for c in miss: ws.update_cell(1, nxt, c); nxt+=1
        
        # Guardar datos en orden
        ws.append_row(datos)
        return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False

# --- INTERFAZ ---
def show(sheet):
    st.title("🔐 Cierre de Caja Diario")
    st.caption("Cuadre de efectivo y registro de ahorro del día.")
    st.markdown("---")
    
    if not sheet: return

    hoy = datetime.now(ZONA_HORARIA).date()
    col_f, col_s = st.columns([1, 2])
    fecha_cierre = col_f.date_input("Fecha de Arqueo", value=hoy)
    fecha_str = fecha_cierre.strftime("%Y-%m-%d")

    datos_cierre = verificar_cierre_existente(sheet, fecha_str)

    # --- YA CERRADO ---
    if datos_cierre is not None:
        z = datos_cierre.get("Numero_Cierre_Loyverse", "S/N")
        with col_s: st.success(f"✅ **DÍA CERRADO** (Z: {z})")
        
        teorico = float(limpiar_numero(datos_cierre.get("Saldo_Teorico_Efectivo", 0)))
        real = float(limpiar_numero(datos_cierre.get("Saldo_Real_Contado", 0)))
        diff = float(limpiar_numero(datos_cierre.get("Diferencia", 0)))
        profit = float(limpiar_numero(datos_cierre.get("Profit_Retenido", 0)))
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Debía Haber", formato_moneda_co(teorico))
        c2.metric("Se Contó", formato_moneda_co(real))
        c3.metric("Diferencia", formato_moneda_co(diff), delta_color="off")
        
        st.info(f"🐷 Ahorro registrado: **{formato_moneda_co(profit)}** ({datos_cierre.get('Estado_Ahorro','-')})")
        
        if st.button("🗑️ REABRIR CAJA", type="secondary"):
            if reabrir_caja(sheet, fecha_str): st.success("Reabierto."); time.sleep(1); st.rerun()

    # --- PENDIENTE ---
    else:
        with col_s: st.warning("⚠️ **PENDIENTE**")
        df_ventas, df_g, df_c, ws_v = cargar_movimientos(sheet, fecha_str)

        v_total=0; v_ef=0; v_dig=0; v_tar=0; g_ef=0; c_ef=0

        if df_ventas is not None and not df_ventas.empty:
            # Auditoría
            with st.expander("🛠️ Auditoría Pagos (Corregir Efectivo vs Nequi)", expanded=False):
                df_aud = df_ventas[["Hora","Numero_Recibo","Total_Dinero","Metodo_Pago_Loyverse","Metodo_Pago_Real_Auditado"]].drop_duplicates(subset=["Numero_Recibo"])
                df_ed = st.data_editor(df_aud, column_config={"Metodo_Pago_Real_Auditado": st.column_config.SelectboxColumn("MÉTODO REAL", options=["Efectivo","Nequi","Tarjeta","Otro"], required=True)}, hide_index=True, use_container_width=True)
                if st.button("💾 Guardar Correcciones"):
                    if actualizar_metodos_pago(ws_v, df_ed): st.success("Listo."); st.rerun()

            v_total = df_ventas["Total_Dinero"].sum()
            v_ef = df_ventas[df_ventas["Metodo_Pago_Real_Auditado"]=="Efectivo"]["Total_Dinero"].sum()
            v_dig = df_ventas[df_ventas["Metodo_Pago_Real_Auditado"].str.contains("Nequi|Davi|Banco", case=False)]["Total_Dinero"].sum()
            v_tar = df_ventas[df_ventas["Metodo_Pago_Real_Auditado"].isin(["Tarjeta","Datafono"])]["Total_Dinero"].sum()
            
            g_ef = df_g[df_g["Metodo_Pago"].str.contains("Efectivo", case=False)]["Monto"].sum() if not df_g.empty else 0
            c_ef = df_c[df_c["Metodo_Pago"].str.contains("Efectivo", case=False)]["Precio_Total_Pagado"].sum() if not df_c.empty else 0

        saldo_teo = v_ef - g_ef - c_ef

        # Resumen
        st.markdown("#### Resumen Financiero")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("VENTA TOTAL", formato_moneda_co(v_total))
        k2.metric("Efectivo", formato_moneda_co(v_ef))
        k3.metric("Digital", formato_moneda_co(v_dig))
        k4.metric("Tarjetas", formato_moneda_co(v_tar))
        
        st.markdown("---")
        
        # --- PROFIT FIRST MANUAL ---
        st.subheader("💰 Fondo de Ahorro (Profit First)")
        c_p1, c_p2 = st.columns([1, 2])
        
        pct_sug = c_p1.number_input("% Meta Ahorro", value=5, min_value=0)
        sugerido = v_total * (pct_sug/100)
        
        with c_p2:
            st.caption(f"Sugerido matemático: {formato_moneda_co(sugerido)}")
            # CAMPO LIBRE: Tú decides cuánto ahorras hoy
            monto_real_ahorro = st.number_input("💵 MONTO A GUARDAR HOY:", value=float(sugerido), step=1000.0)
            
            # Estado
            estado_ahorro = st.radio("Estado:", ["🔴 PENDIENTE (Debo transferir luego)", "🟢 GUARDADO (Ya transferí)"], horizontal=True)

        st.markdown("---")
        
        # ARQUEO
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
            elif diff > 0: st.info(f"🔵 SOBRA: {formato_moneda_co(diff)}")
            else: st.error(f"🔴 FALTA: {formato_moneda_co(diff)}")

        c_z, c_n = st.columns([1, 2])
        z = c_z.text_input("Z-Report")
        notas = c_n.text_area("Notas")
        
        if st.button("🔒 CERRAR CAJA", type="primary", use_container_width=True):
            est_final = "GUARDADO" if "🟢" in estado_ahorro else "PENDIENTE"
            if monto_real_ahorro == 0: est_final = "N/A"
            
            # Guardamos exactamente lo que escribiste en monto_real_ahorro
            datos = [
                fecha_str, datetime.now(ZONA_HORARIA).strftime("%H:%M"),
                v_total, v_ef, (g_ef+c_ef), saldo_teo, real, diff, 
                v_dig, v_tar, notas, 
                monto_real_ahorro, # Valor Manual
                est_final, str(z)
            ]
            if guardar_cierre(sheet, datos):
                st.balloons(); st.success("Guardado."); st.cache_data.clear(); time.sleep(2); st.rerun()
