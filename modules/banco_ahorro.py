import streamlit as st
import pandas as pd
from datetime import datetime
import time
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
        # 1. Cargar Cierres (Entradas de dinero)
        ws_c = sheet.worksheet(HOJA_CIERRES)
        df_c = leer_datos_seguro(ws_c)
        
        # 2. Cargar Retiros (Salidas de dinero)
        try:
            ws_r = sheet.worksheet(HOJA_RETIROS)
            df_r = leer_datos_seguro(ws_r)
        except:
            ws_r = sheet.add_worksheet(title=HOJA_RETIROS, rows="1000", cols="10")
            ws_r.append_row(HEADERS_RETIROS)
            df_r = pd.DataFrame(columns=HEADERS_RETIROS)

        return df_c, df_r, ws_c, ws_r
    except: return None, None, None, None

def registrar_retiro(ws_r, monto, motivo, responsable):
    try:
        fecha = datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d")
        hora = datetime.now(ZONA_HORARIA).strftime("%H:%M")
        ws_r.append_row([generar_id(), fecha, hora, monto, motivo, responsable])
        return True
    except: return False

def actualizar_estado_pago(ws_c, fecha_pago):
    """Busca la fecha y cambia PENDIENTE por GUARDADO"""
    try:
        fechas = ws_c.col_values(1) # Columna A
        try:
            fila = fechas.index(str(fecha_pago)) + 1
        except: return False
        
        # Buscar columna Estado_Ahorro
        headers = ws_c.row_values(1)
        try: col = headers.index("Estado_Ahorro") + 1
        except: col = 10
        
        ws_c.update_cell(fila, col, "GUARDADO")
        return True
    except: return False

def show(sheet):
    st.title("🐷 Banco de Ahorro (Profit First)")
    st.caption("Gestión de utilidades y reservas.")
    st.markdown("---")
    
    if not sheet: return

    df_c, df_r, ws_c, ws_r = cargar_datos(sheet)

    if df_c is None or df_c.empty:
        st.info("No hay cierres de caja registrados aún.")
        return

    # --- PROCESAMIENTO MATEMÁTICO ROBUSTO ---
    # Convertimos todo a números limpios para evitar errores de $
    df_c["Profit_Num"] = df_c["Profit_Retenido"].astype(str).apply(limpiar_numero)
    
    if not df_r.empty:
        df_r["Monto_Num"] = df_r["Monto_Retirado"].astype(str).apply(limpiar_numero)
        total_retiros = df_r["Monto_Num"].sum()
    else:
        total_retiros = 0

    # Clasificar Entradas
    guardados = df_c[df_c["Estado_Ahorro"] == "GUARDADO"]["Profit_Num"].sum()
    pendientes = df_c[df_c["Estado_Ahorro"] == "PENDIENTE"]["Profit_Num"].sum()
    
    saldo_disponible = guardados - total_retiros

    # --- DASHBOARD ---
    k1, k2, k3 = st.columns(3)
    k1.metric("💰 SALDO DISPONIBLE", formato_moneda(saldo_disponible), help="Dinero real en la cuenta.")
    k2.metric("📥 Total Acumulado Histórico", formato_moneda(guardados))
    k3.metric("⚠️ Deuda por Transferir", formato_moneda(pendientes), delta_color="inverse")

    st.markdown("---")

    tab_pend, tab_ret, tab_hist = st.tabs(["🟠 PAGAR PENDIENTES", "💸 RETIRAR FONDOS", "📜 HISTORIAL"])

    # TAB 1: PAGAR LO QUE SE DEBE
    with tab_pend:
        df_pend = df_c[df_c["Estado_Ahorro"] == "PENDIENTE"].copy()
        
        if not df_pend.empty:
            st.info("Estos días se cerró caja pero NO se transfirió el ahorro. Pónte al día aquí:")
            
            # Crear lista seleccionable
            df_pend["Texto"] = df_pend.apply(lambda x: f"{x['Fecha']} | {formato_moneda(x['Profit_Num'])}", axis=1)
            opcion = st.selectbox("Selecciona deuda a pagar:", df_pend["Texto"].tolist())
            
            if st.button("✅ YA REALICÉ LA TRANSFERENCIA"):
                fecha_sel = opcion.split(" | ")[0]
                with st.spinner("Actualizando base de datos..."):
                    if actualizar_estado_pago(ws_c, fecha_sel):
                        st.balloons()
                        st.success("¡Pago registrado! El dinero entró al saldo.")
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("Error al actualizar.")
        else:
            st.success("🎉 ¡Estás al día! No tienes ahorros pendientes por transferir.")

    # TAB 2: RETIRAR
    with tab_ret:
        st.write("Registra salidas de dinero del fondo de ahorro (Inversiones, Reparto, Emergencias).")
        
        c1, c2 = st.columns(2)
        monto_ret = c1.number_input("Monto a Retirar", min_value=0.0, step=50000.0)
        motivo = c2.text_input("Motivo del Retiro")
        resp = st.text_input("Responsable")
        
        if st.button("🚨 CONFIRMAR RETIRO", type="primary"):
            if 0 < monto_ret <= saldo_disponible:
                if registrar_retiro_profit(ws_r, monto_ret, motivo, resp):
                    st.success("Retiro exitoso.")
                    time.sleep(2)
                    st.rerun()
            else:
                st.error("Fondos insuficientes o monto inválido.")

    # TAB 3: HISTORIAL
    with tab_hist:
        col_h1, col_h2 = st.columns(2)
        
        with col_h1:
            st.write("📥 **Entradas (Ahorros)**")
            st.dataframe(df_c[df_c["Profit_Num"] > 0][["Fecha", "Profit_Retenido", "Estado_Ahorro"]].sort_values("Fecha", ascending=False), use_container_width=True, hide_index=True)
            
        with col_h2:
            st.write("📤 **Salidas (Retiros)**")
            if not df_r.empty:
                st.dataframe(df_r[["Fecha", "Monto_Retirado", "Motivo"]].sort_values("Fecha", ascending=False), use_container_width=True, hide_index=True)
            else:
                st.info("Sin retiros.")
