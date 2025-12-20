import streamlit as st
import pandas as pd
from datetime import datetime, date
import time
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero

HOJA_VENTAS = "LOG_VENTAS_LOYVERSE"
HOJA_GASTOS = "LOG_GASTOS"
HOJA_COMPRAS = "LOG_COMPRAS"
HOJA_CIERRES = "LOG_CIERRES_CAJA"

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
        current = ws.row_values(1)
        if not current: ws.append_row(HEADERS_CIERRE); return
        miss = [c for c in HEADERS_CIERRE if c not in current]
        if miss:
            nxt = len(current) + 1
            for c in miss: ws.update_cell(1, nxt, c); nxt += 1
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

def cargar_movimientos(sheet, fecha):
    try:
        ws_v = sheet.worksheet(HOJA_VENTAS); df_v = pd.DataFrame(ws_v.get_all_records())
        if not df_v.empty:
            df_v["Fecha"] = df_v["Fecha"].astype(str)
            df_v = df_v[df_v["Fecha"] == fecha]
            df_v = df_v.drop_duplicates(subset=["Numero_Recibo", "ID_Plato", "Hora"])
            df_v["Total_Dinero"] = pd.to_numeric(df_v["Total_Dinero"], errors='coerce').fillna(0)
        
        try: ws_g = sheet.worksheet(HOJA_GASTOS); df_g = leer_datos_seguro(ws_g)
        except: df_g = pd.DataFrame()
        if not df_g.empty:
            df_g["Fecha"] = df_g["Fecha"].astype(str)
            df_g = df_g[df_g["Fecha"] == fecha]
            df_g["Monto"] = pd.to_numeric(df_g["Monto"], errors='coerce').fillna(0)

        try: ws_c = sheet.worksheet(HOJA_COMPRAS); df_c = leer_datos_seguro(ws_c)
        except: df_c = pd.DataFrame()
        if not df_c.empty:
            df_c["Fecha_Registro"] = df_c["Fecha_Registro"].astype(str)
            df_c = df_c[df_c["Fecha_Registro"] == fecha]
            df_c["Precio_Total_Pagado"] = pd.to_numeric(df_c["Precio_Total_Pagado"], errors='coerce').fillna(0)
            
        return df_v, df_g, df_c
    except: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

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
    except: return False

def reabrir(sheet, fecha):
    try:
        ws = sheet.worksheet(HOJA_CIERRES)
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        df = df[df["Fecha"] != fecha]
        ws.clear()
        ws.update([df.columns.values.tolist()] + df.values.tolist())
        return True
    except: return False

# --- INTERFAZ ---
def show(sheet):
    st.title("🔐 Cierre de Caja Diario")
    st.markdown("---")
    if not sheet: return

    hoy = datetime.now(ZONA_HORARIA).date()
    fecha_cierre = st.date_input("Fecha", value=hoy)
    fecha_str = fecha_cierre.strftime("%Y-%m-%d")

    datos = verificar_cierre(sheet, fecha_str)

    if datos is not None:
        st.success(f"✅ DÍA CERRADO (Z: {datos.get('Numero_Cierre_Loyverse','-')})")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Debía Haber", formato_moneda_co(datos.get("Saldo_Teorico_Efectivo")))
        c2.metric("Se Contó", formato_moneda_co(datos.get("Saldo_Real_Contado")))
        c3.metric("Diferencia", formato_moneda_co(datos.get("Diferencia")), delta_color="off")
        
        st.info(f"🐷 Ahorro: {formato_moneda_co(datos.get('Profit_Retenido'))} ({datos.get('Estado_Ahorro')})")
        
        if st.button("🗑️ REABRIR CAJA"):
            if reabrir(sheet, fecha_str): st.success("Listo"); time.sleep(1); st.rerun()
    else:
        st.warning("⚠️ PENDIENTE DE CIERRE")
        df_v, df_g, df_c = cargar_movimientos(sheet, fecha_str)

        if df_v.empty:
            st.error("No hay ventas. Descarga primero.")
        else:
            # Cálculos
            v_tot = df_v["Total_Dinero"].sum()
            v_ef = df_v[df_v["Metodo_Pago_Real_Auditado"]=="Efectivo"]["Total_Dinero"].sum()
            v_dig = df_v[df_v["Metodo_Pago_Real_Auditado"].str.contains("Nequi|Davi|Banco|Transf", case=False)]["Total_Dinero"].sum()
            v_tar = df_v[df_v["Metodo_Pago_Real_Auditado"].isin(["Tarjeta","Datafono"])]["Total_Dinero"].sum()
            
            g_ef = df_g[df_g["Metodo_Pago"].str.contains("Efectivo", case=False)]["Monto"].sum() if not df_g.empty else 0
            c_ef = df_c[df_c["Metodo_Pago"].str.contains("Efectivo", case=False)]["Precio_Total_Pagado"].sum() if not df_c.empty else 0
            
            saldo_teo = v_ef - g_ef - c_ef

            # 1. RESUMEN
            st.write("#### 1. Resumen Financiero")
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Total", formato_moneda_co(v_tot))
            k2.metric("Efectivo", formato_moneda_co(v_ef))
            k3.metric("Digital", formato_moneda_co(v_dig))
            k4.metric("Tarjetas", formato_moneda_co(v_tar))

            st.markdown("---")
            
            # 2. AHORRO (Solo calcular)
            st.write("#### 2. Cálculo de Ahorro")
            c_a1, c_a2 = st.columns([1, 2])
            pct = c_a1.number_input("% Profit", value=5)
            monto_p = st.number_input("Monto a Ahorrar (Editable)", value=float(v_tot * (pct/100)), step=1000.0)
            
            estado_ahorro = st.radio("Estado de Transferencia:", ["🔴 PENDIENTE", "🟢 GUARDADO (Ya transferí)"], horizontal=True)

            st.markdown("---")

            # 3. ARQUEO
            st.write("#### 3. Conteo de Billetes")
            c1, c2, c3 = st.columns(3)
            c1.metric("(+) Entradas", formato_moneda_co(v_ef))
            c2.metric("(-) Salidas", formato_moneda_co(g_ef + c_ef))
            c3.metric("(=) TEÓRICO", formato_moneda_co(saldo_teo))
            
            real = st.number_input("¿Cuánto contaste?", min_value=0.0, step=500.0)
            diff = real - saldo_teo
            
            if diff == 0: st.success("✅ CUADRADO")
            else: st.error(f"Diferencia: {formato_moneda_co(diff)}")

            c_z, c_n = st.columns([1, 2])
            z = c_z.text_input("Z-Report")
            notas = c_n.text_area("Notas")

            if st.button("🔒 GUARDAR CIERRE", type="primary", use_container_width=True):
                est = "GUARDADO" if "🟢" in estado_ahorro else "PENDIENTE"
                d = {
                    "Fecha": fecha_str, "Hora_Cierre": datetime.now(ZONA_HORARIA).strftime("%H:%M"),
                    "Venta_Total_Bruta": v_tot, "Venta_Efectivo": v_ef, "Gastos_Pagados_Efectivo": g_ef+c_ef,
                    "Saldo_Teorico_Efectivo": saldo_teo, "Saldo_Real_Contado": real, "Diferencia": diff,
                    "Total_Nequi": v_dig, "Total_Tarjetas": v_tar, "Notas": notas,
                    "Profit_Retenido": monto_p, "Estado_Ahorro": est, "Numero_Cierre_Loyverse": str(z)
                }
                if guardar_cierre(sheet, d):
                    st.balloons(); st.success("Guardado."); time.sleep(2); st.rerun()

    # HISTORIAL
    st.markdown("---")
    with st.expander("📜 Ver Historial de Cierres", expanded=False):
        try:
            ws = sheet.worksheet(HOJA_CIERRES)
            df = leer_datos_seguro(ws)
            if not df.empty:
                st.dataframe(df.sort_values("Fecha", ascending=False), use_container_width=True)
        except: pass
