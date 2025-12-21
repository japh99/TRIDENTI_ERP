import streamlit as st
import pandas as pd
from datetime import datetime
import time
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero, generar_id

# --- CONFIGURACIÓN DE HOJAS (Nombres exactos de tus pestañas) ---
HOJA_CIERRES = "LOG_CIERRES_CAJA"
HOJA_ABONOS = "LOG_ABONOS_PROFIT"
HOJA_RETIROS = "LOG_RETIROS_PROFIT"

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

# --- FUNCIONES DE BASE DE DATOS ---

def cargar_datos_banco(sheet):
    try:
        # 1. Cargar Cierres
        ws_c = sheet.worksheet(HOJA_CIERRES)
        df_c = leer_datos_seguro(ws_c)
        
        # 2. Cargar Abonos
        ws_a = sheet.worksheet(HOJA_ABONOS)
        df_a = leer_datos_seguro(ws_a)
        
        # 3. Cargar Retiros
        ws_r = sheet.worksheet(HOJA_RETIROS)
        df_r = leer_datos_seguro(ws_r)

        # Limpieza Cierres (Usando Profit_Retenido según tu imagen)
        if not df_c.empty:
            col_p = "Profit_Retenido"
            if col_p in df_c.columns:
                df_c["Monto_Sugerido"] = pd.to_numeric(df_c[col_p].astype(str).apply(limpiar_numero), errors='coerce').fillna(0)
            else:
                df_c["Monto_Sugerido"] = 0
            
            if "Estado_Ahorro" not in df_c.columns: 
                df_c["Estado_Ahorro"] = "Pendiente"
        
        # Limpieza Abonos (Monto_Abonado)
        if not df_a.empty and "Monto_Abonado" in df_a.columns:
            df_a["Monto_Abonado"] = pd.to_numeric(df_a["Monto_Abonado"].astype(str).apply(limpiar_numero), errors='coerce').fillna(0)
        
        # Limpieza Retiros (Monto_Retirado)
        if not df_r.empty and "Monto_Retirado" in df_r.columns:
            df_r["Monto_Retirado"] = pd.to_numeric(df_r["Monto_Retirado"].astype(str).apply(limpiar_numero), errors='coerce').fillna(0)

        return df_c, df_a, df_r, ws_c, ws_a, ws_r
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), None, None, None

def registrar_abono(ws_a, fecha_cierre, monto, resp):
    try:
        # ID, Fecha, Hora, Fecha_Cierre_O, Monto_Abonado, Responsable
        fila = [
            generar_id(),
            datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d"),
            datetime.now(ZONA_HORARIA).strftime("%H:%M"),
            str(fecha_cierre),
            monto,
            resp
        ]
        ws_a.append_row(fila)
        return True
    except: return False

def registrar_retiro(ws_r, monto, motivo, resp):
    try:
        # ID, Fecha, Hora, Monto_Retirado, Motivo, Responsable
        fila = [
            generar_id(),
            datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d"),
            datetime.now(ZONA_HORARIA).strftime("%H:%M"),
            monto,
            motivo,
            resp
        ]
        ws_r.append_row(fila)
        return True
    except: return False

def marcar_cierre_como_ahorrado(ws_c, fecha_cierre):
    try:
        fechas = ws_c.col_values(1) # Fecha está en Col A
        if str(fecha_cierre) in fechas:
            row_idx = fechas.index(str(fecha_cierre)) + 1
            headers = ws_c.row_values(1)
            if "Estado_Ahorro" in headers:
                col_idx = headers.index("Estado_Ahorro") + 1
                ws_c.update_cell(row_idx, col_idx, "Ahorrado")
    except: pass

# --- INTERFAZ ---

def show(sheet):
    st.title("🐷 Banco de Ahorro (Profit First)")
    
    if not sheet: return

    df_c, df_a, df_r, ws_c, ws_a, ws_r = cargar_datos_banco(sheet)

    # --- CÁLCULOS ---
    total_ahorrado = df_a["Monto_Abonado"].sum() if not df_a.empty and "Monto_Abonado" in df_a.columns else 0
    total_retirado = df_r["Monto_Retirado"].sum() if not df_r.empty and "Monto_Retirado" in df_r.columns else 0
    saldo_disponible = total_ahorrado - total_retirado

    pendientes = df_c[df_c["Estado_Ahorro"] != "Ahorrado"].copy() if not df_c.empty else pd.DataFrame()
    deuda_pendiente = pendientes["Monto_Sugerido"].sum() if not pendientes.empty else 0

    # DASHBOARD
    c1, c2, c3 = st.columns(3)
    c1.metric("💰 Saldo Disponible", formato_moneda(saldo_disponible))
    c2.metric("⚠️ Pendiente por Guardar", formato_moneda(deuda_pendiente))
    c3.metric("💸 Total Retirado", formato_moneda(total_retirado))

    st.markdown("---")
    t1, t2, t3 = st.tabs(["📥 INGRESAR AHORRO", "📤 REGISTRAR RETIRO", "📜 HISTORIAL"])

    with t1:
        st.subheader("Registrar entrada de dinero")
        if not pendientes.empty:
            opciones = pendientes.apply(lambda x: f"{x['Fecha']} | Sugerido: {formato_moneda(x['Monto_Sugerido'])}", axis=1).tolist()
            seleccion = st.selectbox("¿A qué día corresponde este ahorro?", opciones)
            
            fecha_sel = seleccion.split(" | ")[0]
            monto_sug = pendientes[pendientes["Fecha"] == fecha_sel].iloc[0]["Monto_Sugerido"]

            col_a, col_b = st.columns(2)
            monto_real = col_a.number_input("Cantidad real a ahorrar", value=float(monto_sug), step=1000.0)
            responsable = col_b.text_input("Responsable", value="Admin")
            
            marcar_completado = st.checkbox("Marcar día como 'Totalmente Ahorrado'", value=True)

            if st.button("✅ GUARDAR ABONO"):
                if monto_real > 0:
                    if registrar_abono(ws_a, fecha_sel, monto_real, responsable):
                        if marcar_completado:
                            marcar_cierre_como_ahorrado(ws_c, fecha_sel)
                        st.success("Abono registrado correctamente.")
                        time.sleep(1); st.rerun()
        else:
            st.success("🎉 ¡No hay ahorros pendientes!")

    with t2:
        st.subheader("Registrar salida de dinero")
        r1, r2 = st.columns(2)
        monto_ret = r1.number_input("Monto a retirar", min_value=0.0, step=5000.0)
        motivo = r2.text_input("Motivo del retiro")
        resp_ret = st.text_input("Autorizado por", key="resp_ret")

        if st.button("🚨 EJECUTAR RETIRO"):
            if 0 < monto_ret <= saldo_disponible:
                if registrar_retiro(ws_r, monto_ret, motivo, resp_ret):
                    st.success("Retiro registrado."); time.sleep(1); st.rerun()
            else:
                st.error("Saldo insuficiente o monto inválido.")

    with t3:
        st.subheader("Historial de Movimientos")
        
        historial_list = []

        # Procesar Entradas
        if not df_a.empty:
            for _, fila in df_a.iterrows():
                historial_list.append({
                    "Fecha": fila.get("Fecha", "N/A"),
                    "Tipo": "ENTRADA",
                    "Monto": fila.get("Monto_Abonado", 0),
                    "Referencia": f"Cierre {fila.get('Fecha_Cierre_O', '')}",
                    "Responsable": fila.get("Responsable", "")
                })

        # Procesar Salidas
        if not df_r.empty:
            for _, fila in df_r.iterrows():
                historial_list.append({
                    "Fecha": fila.get("Fecha", "N/A"),
                    "Tipo": "SALIDA",
                    "Monto": fila.get("Monto_Retirado", 0),
                    "Referencia": fila.get("Motivo", ""),
                    "Responsable": fila.get("Responsable", "")
                })

        if historial_list:
            df_hist = pd.DataFrame(historial_list)
            df_hist = df_hist.sort_values("Fecha", ascending=False)
            
            # Formatear Moneda
            df_hist["Monto"] = df_hist["Monto"].apply(formato_moneda)
            
            def color_tipo(val):
                color = 'green' if val == "ENTRADA" else 'red'
                return f'color: {color}; font-weight: bold'

            st.dataframe(
                df_hist[["Fecha", "Tipo", "Monto", "Referencia", "Responsable"]]
                .style.applymap(color_tipo, subset=["Tipo"]),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No hay movimientos registrados.")
