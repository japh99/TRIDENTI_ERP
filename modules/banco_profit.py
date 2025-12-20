import streamlit as st
import pandas as pd
from datetime import datetime
import time
import uuid
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero, generar_id

HOJA_CIERRES = "LOG_CIERRES_CAJA"
HOJA_RETIROS = "LOG_RETIROS_PROFIT"
HEADERS_RETIROS = ["ID", "Fecha", "Hora", "Monto_Retirado", "Motivo", "Responsable"]

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

def cargar_datos(sheet):
    try:
        ws_c = sheet.worksheet(HOJA_CIERRES)
        df_c = leer_datos_seguro(ws_c)
        if not df_c.empty and "Profit_Retenido" in df_c.columns:
            df_c["Profit_Num"] = df_c["Profit_Retenido"].astype(str).apply(limpiar_numero)
        
        try:
            ws_r = sheet.worksheet(HOJA_RETIROS)
            df_r = leer_datos_seguro(ws_r)
            if not df_r.empty and "Monto_Retirado" in df_r.columns:
                df_r["Monto_Num"] = df_r["Monto_Retirado"].astype(str).apply(limpiar_numero)
        except:
            ws_r = sheet.add_worksheet(title=HOJA_RETIROS, rows="1000", cols="6")
            ws_r.append_row(HEADERS_RETIROS)
            df_r = pd.DataFrame()

        return df_c, df_r, ws_c, ws_r
    except: return pd.DataFrame(), pd.DataFrame(), None, None

def pagar_ahorro(ws, fecha):
    try:
        fechas = ws.col_values(1)
        idx = fechas.index(str(fecha)) + 1
        head = ws.row_values(1)
        col = head.index("Estado_Ahorro") + 1
        ws.update_cell(idx, col, "GUARDADO")
        return True
    except: return False

def retirar(ws, monto, mot, resp):
    try:
        f = datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d")
        h = datetime.now(ZONA_HORARIA).strftime("%H:%M")
        ws.append_row([generar_id(), f, h, monto, mot, resp])
        return True
    except: return False

def show(sheet):
    st.title("🐷 Banco de Ahorro (Profit First)")
    st.caption("Gestión de utilidades y reservas.")
    st.markdown("---")
    
    if not sheet: return
    df_c, df_r, ws_c, ws_r = cargar_datos(sheet)

    if df_c.empty:
        st.info("Sin datos.")
        return

    # Cálculos
    total_guardado = df_c[df_c["Estado_Ahorro"] == "GUARDADO"]["Profit_Num"].sum()
    total_retirado = df_r["Monto_Num"].sum() if not df_r.empty else 0
    saldo = total_guardado - total_retirado
    
    pendientes = df_c[df_c["Estado_Ahorro"] == "PENDIENTE"]
    total_deuda = pendientes["Profit_Num"].sum()

    k1, k2, k3 = st.columns(3)
    k1.metric("💰 SALDO DISPONIBLE", formato_moneda(saldo))
    k2.metric("📥 Acumulado Histórico", formato_moneda(total_guardado))
    k3.metric("⚠️ Deuda por Transferir", formato_moneda(total_deuda), delta_color="inverse")

    st.markdown("---")
    t1, t2, t3 = st.tabs(["🟠 PAGAR DEUDA", "💸 RETIRAR", "📜 HISTORIAL"])

    with t1:
        if not pendientes.empty:
            lista = pendientes.apply(lambda x: f"{x['Fecha']} | {formato_moneda(x['Profit_Num'])}", axis=1).tolist()
            sel = st.selectbox("Selecciona:", lista)
            if st.button("✅ YA HICE LA TRANSFERENCIA"):
                if pagar_ahorro(ws_c, sel.split(" | ")[0]):
                    st.success("Pagado."); st.cache_data.clear(); time.sleep(2); st.rerun()
        else: st.success("¡Al día!")

    with t2:
        c1, c2 = st.columns(2)
        m = c1.number_input("Monto", step=50000.0)
        mot = c2.text_input("Motivo")
        resp = c2.text_input("Responsable")
        if st.button("🚨 RETIRAR FONDOS", type="primary"):
            if 0 < m <= saldo:
                if retirar(ws_r, m, mot, resp):
                    st.success("Listo."); st.cache_data.clear(); time.sleep(2); st.rerun()
            else: st.error("Fondos insuficientes.")

    with t3:
        st.write("**Entradas**")
        st.dataframe(df_c[["Fecha", "Profit_Retenido", "Estado_Ahorro"]].sort_values("Fecha", ascending=False), use_container_width=True)
        if not df_r.empty:
            st.write("**Salidas**")
            st.dataframe(df_r[["Fecha", "Monto_Retirado", "Motivo"]].sort_values("Fecha", ascending=False), use_container_width=True)
