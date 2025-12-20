import streamlit as st
import pandas as pd
from datetime import datetime
import time
import uuid
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero, generar_id

HOJA_CIERRES = "LOG_CIERRES_CAJA"
HOJA_RETIROS = "LOG_RETIROS_PROFIT"
# Nueva hoja para abonos parciales (Flexibilidad total)
HOJA_ABONOS = "LOG_ABONOS_PROFIT" 

HEADERS_RETIROS = ["ID", "Fecha", "Hora", "Monto", "Motivo", "Responsable"]
HEADERS_ABONOS = ["ID", "Fecha", "Hora", "Fecha_Cierre_Origen", "Monto_Abonado", "Responsable"]

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

def cargar_datos(sheet):
    try:
        ws_c = sheet.worksheet(HOJA_CIERRES)
        df_c = leer_datos_seguro(ws_c)
        
        # Crear hojas si no existen
        try: ws_r = sheet.worksheet(HOJA_RETIROS)
        except: ws_r = sheet.add_worksheet(title=HOJA_RETIROS, rows="1000", cols="10"); ws_r.append_row(HEADERS_RETIROS)
        df_r = leer_datos_seguro(ws_r)
        
        try: ws_a = sheet.worksheet(HOJA_ABONOS)
        except: ws_a = sheet.add_worksheet(title=HOJA_ABONOS, rows="1000", cols="10"); ws_a.append_row(HEADERS_ABONOS)
        df_a = leer_datos_seguro(ws_a)

        return df_c, df_r, df_a, ws_a, ws_r
    except: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), None, None

def registrar_abono(sheet, fecha_origen, monto, resp):
    try:
        ws = sheet.worksheet(HOJA_ABONOS)
        f = datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d")
        h = datetime.now(ZONA_HORARIA).strftime("%H:%M")
        ws.append_row([generar_id(), f, h, fecha_origen, monto, resp])
        
        # Marcar cierre como saldado (Opcional, pero para limpiar la lista)
        # Aquí asumimos que si abona algo, esa fecha ya se "tocó". 
        # Si quieres control estricto de saldos pendientes, sería más complejo.
        # Por simplicidad V7: Marcamos el día como "PROCESADO" en Cierres.
        ws_c = sheet.worksheet(HOJA_CIERRES)
        fechas = ws_c.col_values(1)
        try: 
            idx = fechas.index(str(fecha_origen)) + 1
            headers = ws_c.row_values(1)
            col_idx = headers.index("Estado_Ahorro") + 1
            ws_c.update_cell(idx, col_idx, "PROCESADO")
        except: pass
            
        return True
    except: return False

def registrar_retiro(ws, monto, mot, resp):
    try:
        f = datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d")
        h = datetime.now(ZONA_HORARIA).strftime("%H:%M")
        ws.append_row([generar_id(), f, h, monto, mot, resp])
        return True
    except: return False

def show(sheet):
    st.title("🐷 Banco de Ahorro (Profit First)")
    st.markdown("---")
    if not sheet: return

    df_c, df_r, df_a, ws_a, ws_r = cargar_datos(sheet)

    # CÁLCULOS REALES
    # Saldo = Total Abonos - Total Retiros
    if not df_a.empty:
        df_a["Monto_Abonado"] = df_a["Monto_Abonado"].astype(str).apply(limpiar_numero)
        total_ingresos = df_a["Monto_Abonado"].sum()
    else: total_ingresos = 0

    if not df_r.empty:
        df_r["Monto"] = df_r["Monto"].astype(str).apply(limpiar_numero)
        total_egresos = df_r["Monto"].sum()
    else: total_egresos = 0
    
    saldo_actual = total_ingresos - total_egresos

    # Deuda Pendiente (Días cerrados no procesados)
    total_deuda = 0
    pendientes = pd.DataFrame()
    if not df_c.empty:
        df_c["Profit_Num"] = df_c["Profit_Retenido"].astype(str).apply(limpiar_numero)
        pendientes = df_c[df_c["Estado_Ahorro"] == "PENDIENTE"]
        total_deuda = pendientes["Profit_Num"].sum()

    # DASHBOARD
    k1, k2, k3 = st.columns(3)
    k1.metric("💰 SALDO DISPONIBLE", formato_moneda(saldo_actual))
    k2.metric("📥 Total Histórico", formato_moneda(total_ingresos))
    k3.metric("⚠️ Sugerido Pendiente", formato_moneda(total_deuda), delta_color="inverse")

    st.markdown("---")
    t1, t2, t3 = st.tabs(["🟠 INGRESAR DINERO", "💸 RETIRAR DINERO", "📜 EXTRACTO"])

    # TAB 1: INGRESOS (Pagar Deuda)
    with t1:
        if not pendientes.empty:
            st.info("Selecciona un cierre pendiente para transferir el dinero al banco.")
            lista = pendientes.apply(lambda x: f"{x['Fecha']} | Sugerido: {formato_moneda(x['Profit_Num'])}", axis=1).tolist()
            sel = st.selectbox("Cierre:", lista)
            
            # Recuperar monto sugerido
            fecha_sel = sel.split(" | ")[0]
            monto_sug = pendientes[pendientes["Fecha"] == fecha_sel].iloc[0]["Profit_Num"]
            
            # CAMPO EDITABLE (FLEXIBILIDAD TOTAL)
            monto_real = st.number_input("Monto a Transferir (Editable)", value=float(monto_sug), step=10000.0)
            
            if st.button("✅ CONFIRMAR TRANSFERENCIA"):
                if registrar_abono(sheet, fecha_sel, monto_real, "Admin"):
                    st.success("¡Dinero ingresado al Banco!"); time.sleep(2); st.rerun()
        else:
            st.success("No hay cierres pendientes.")
            # Opción de aporte voluntario extra
            if st.checkbox("Hacer aporte voluntario extra"):
                m_extra = st.number_input("Monto Extra", step=10000.0)
                if st.button("Aportar"):
                    if registrar_abono(sheet, "APORTE-EXTRA", m_extra, "Admin"):
                        st.success("Aporte registrado."); time.sleep(2); st.rerun()

    # TAB 2: RETIROS
    with t2:
        c1, c2 = st.columns(2)
        m_ret = c1.number_input("Monto Retiro", step=50000.0)
        mot = c2.text_input("Motivo")
        if st.button("🚨 RETIRAR", type="primary"):
            if 0 < m_ret <= saldo_actual:
                if registrar_retiro(ws_r, m_ret, mot, "Admin"):
                    st.success("Retiro exitoso."); time.sleep(2); st.rerun()
            else: st.error("Fondos insuficientes.")

    # TAB 3: HISTORIAL
    with t3:
        st.write("**Entradas (Abonos)**")
        if not df_a.empty: st.dataframe(df_a[["Fecha", "Monto_Abonado", "Fecha_Cierre_Origen"]].sort_values("Fecha", ascending=False), use_container_width=True)
        st.write("**Salidas (Retiros)**")
        if not df_r.empty: st.dataframe(df_r[["Fecha", "Monto", "Motivo"]].sort_values("Fecha", ascending=False), use_container_width=True)
        
