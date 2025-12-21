import streamlit as st
import pandas as pd
from datetime import datetime
import time
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero, generar_id

HOJA_BANCO = "LOG_BANCO_PROFIT"
HEADERS = ["ID", "Fecha", "Hora", "Tipo", "Monto", "Motivo", "Responsable"]

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

def cargar_banco(sheet):
    try:
        try: ws = sheet.worksheet(HOJA_BANCO)
        except:
            ws = sheet.add_worksheet(title=HOJA_BANCO, rows="1000", cols="10")
            ws.append_row(HEADERS)
        
        df = leer_datos_seguro(ws)
        return df, ws
    except: return pd.DataFrame(), None

def registrar_movimiento(ws, tipo, monto, motivo, resp):
    try:
        fecha = datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d")
        hora = datetime.now(ZONA_HORARIA).strftime("%H:%M")
        # Guardar: ID, Fecha, Hora, Tipo, Monto, Motivo, Responsable
        ws.append_row([generar_id(), fecha, hora, tipo, monto, motivo, resp])
        return True
    except: return False

def show(sheet):
    st.title("🐷 Banco de Ahorro (Profit First)")
    st.caption("Gestión independiente de reservas.")
    st.markdown("---")
    
    if not sheet: return

    df, ws = cargar_banco(sheet)

    # CÁLCULO DE SALDO
    total_ahorrado = 0
    total_retirado = 0
    
    if not df.empty:
        df["Monto"] = pd.to_numeric(df["Monto"], errors='coerce').fillna(0)
        total_ahorrado = df[df["Tipo"] == "ENTRADA"]["Monto"].sum()
        total_retirado = df[df["Tipo"] == "SALIDA"]["Monto"].sum()
    
    saldo = total_ahorrado - total_retirado

    # DASHBOARD
    k1, k2, k3 = st.columns(3)
    k1.metric("💰 SALDO DISPONIBLE", formato_moneda(saldo))
    k2.metric("📥 Total Ahorrado", formato_moneda(total_ahorrado))
    k3.metric("📤 Total Retirado", formato_moneda(total_retirado))

    st.markdown("---")
    
    # ACCIONES
    tab_in, tab_out, tab_hist = st.tabs(["🟢 INGRESAR (AHORRAR)", "🔴 RETIRAR", "📜 EXTRACTO"])

    with tab_in:
        st.write("### Registrar Nuevo Ahorro")
        c1, c2 = st.columns(2)
        monto_in = c1.number_input("Monto a Ahorrar", min_value=0.0, step=10000.0)
        motivo_in = c2.text_input("Nota / Fecha Origen", placeholder="Ej: Ahorro del 20 Dic")
        
        if st.button("✅ CONFIRMAR INGRESO", type="primary"):
            if monto_in > 0:
                if registrar_movimiento(ws, "ENTRADA", monto_in, motivo_in, "Admin"):
                    st.balloons()
                    st.success("¡Dinero guardado!")
                    time.sleep(1); st.rerun()
            else: st.warning("Monto inválido.")

    with tab_out:
        st.write("### Retirar Fondos")
        c3, c4 = st.columns(2)
        monto_out = c3.number_input("Monto a Retirar", min_value=0.0, step=10000.0)
        motivo_out = c4.text_input("Motivo del Retiro", placeholder="Ej: Inversión, Emergencia")
        
        if st.button("🚨 CONFIRMAR RETIRO", type="primary"):
            if 0 < monto_out <= saldo:
                if registrar_movimiento(ws, "SALIDA", monto_out, motivo_out, "Admin"):
                    st.success("Retiro exitoso.")
                    time.sleep(1); st.rerun()
            else: st.error("Fondos insuficientes.")

    with tab_hist:
        st.write("### Movimientos Recientes")
        if not df.empty:
            df_view = df.sort_index(ascending=False).copy()
            df_view["Monto"] = df_view["Monto"].apply(formato_moneda)
            
            # Colores para la tabla
            def color_tipo(val):
                color = "green" if val == "ENTRADA" else "red"
                return f'color: {color}; font-weight: bold'

            st.dataframe(
                df_view[["Fecha", "Tipo", "Monto", "Motivo"]].style.applymap(color_tipo, subset=["Tipo"]),
                use_container_width=True,
                hide_index=True
            )
        else: st.info("Sin movimientos.")
