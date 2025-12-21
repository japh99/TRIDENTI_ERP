import streamlit as st
import pandas as pd
from datetime import datetime
import time
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero, generar_id

# --- CONFIGURACIÓN DE HOJAS ---
HOJA_CIERRES = "LOG_CIERRES_CAJA"
HOJA_ABONOS = "LOG_ABONOS_PROFIT"
HOJA_RETIROS = "LOG_RETIROS_PROFIT"

# Estructura según tus fotos
HEADERS_ABONOS = ["ID", "Fecha", "Hora", "Fecha_Cierre_O", "Monto_Abonado", "Responsable"]
HEADERS_RETIROS = ["ID", "Fecha", "Hora", "Monto_Retirado", "Motivo", "Responsable"]

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

# --- FUNCIONES DE BASE DE DATOS ---

def cargar_datos_banco(sheet):
    try:
        # 1. Cargar Cierres (Deuda)
        ws_c = sheet.worksheet(HOJA_CIERRES)
        df_c = leer_datos_seguro(ws_c)
        
        # 2. Cargar Abonos (Entradas)
        ws_a = sheet.worksheet(HOJA_ABONOS)
        df_a = leer_datos_seguro(ws_a)
        
        # 3. Cargar Retiros (Salidas)
        ws_r = sheet.worksheet(HOJA_RETIROS)
        df_r = leer_datos_seguro(ws_r)

        # Limpieza Cierres
        if not df_c.empty:
            # Detectar columna de profit (ajusta según tu LOG_CIERRES_CAJA)
            col_p = "Profit_Retenido" if "Profit_Retenido" in df_c.columns else "Profit_Sugerido"
            df_c["Monto_Sugerido"] = pd.to_numeric(df_c[col_p].astype(str).apply(limpiar_numero), errors='coerce').fillna(0)
            if "Estado_Ahorro" not in df_c.columns: df_c["Estado_Ahorro"] = "Pendiente"
        
        # Limpieza Abonos
        if not df_a.empty:
            df_a["Monto_Abonado"] = pd.to_numeric(df_a["Monto_Abonado"].astype(str).apply(limpiar_numero), errors='coerce').fillna(0)
        
        # Limpieza Retiros
        if not df_r.empty:
            df_r["Monto_Retirado"] = pd.to_numeric(df_r["Monto_Retirado"].astype(str).apply(limpiar_numero), errors='coerce').fillna(0)

        return df_c, df_a, df_r, ws_c, ws_a, ws_r
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), None, None, None

def registrar_abono(ws_a, fecha_cierre, monto, resp):
    try:
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
        fechas = ws_c.col_values(1) # Asumiendo Fecha en Col A
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

    # --- CÁLCULOS DE SALDOS ---
    total_ahorrado = df_a["Monto_Abonado"].sum() if not df_a.empty else 0
    total_retirado = df_r["Monto_Retirado"].sum() if not df_r.empty else 0
    saldo_disponible = total_ahorrado - total_retirado

    # Días pendientes de ahorro
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
            # 1. Seleccionar el día
            opciones = pendientes.apply(lambda x: f"{x['Fecha']} | Sugerido: {formato_moneda(x['Monto_Sugerido'])}", axis=1).tolist()
            seleccion = st.selectbox("¿A qué día corresponde este ahorro?", opciones)
            
            fecha_sel = seleccion.split(" | ")[0]
            monto_sug = pendientes[pendientes["Fecha"] == fecha_sel].iloc[0]["Monto_Sugerido"]

            # 2. FLEXIBILIDAD: Editar la cantidad
            col_a, col_b = st.columns(2)
            monto_real = col_a.number_input("Cantidad a ahorrar (puedes editarla)", value=float(monto_sug), step=1000.0)
            responsable = col_b.text_input("Responsable", value="Admin")
            
            # 3. Opción de finalizar el día
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
        resp_ret = st.text_input("Autorizado por")

        if st.button("🚨 EJECUTAR RETIRO"):
            if 0 < monto_ret <= saldo_disponible:
                if motivo and resp_ret:
                    if registrar_retiro(ws_r, monto_ret, motivo, resp_ret):
                        st.success("Retiro registrado."); time.sleep(1); st.rerun()
                else:
                    st.warning("Completa motivo y responsable.")
            else:
                st.error("Saldo insuficiente o monto inválido.")

    with t3:
        st.subheader("Historial de Movimientos")
        
        # Crear un historial combinado para ver entradas y salidas
        entradas = df_a[["Fecha", "Monto_Abonado", "Fecha_Cierre_O", "Responsable"]].copy()
        entradas.columns = ["Fecha", "Monto", "Referencia", "Responsable"]
        entradas["Tipo"] = "ENTRADA"

        salidas = df_r[["Fecha", "Monto_Retirado", "Motivo", "Responsable"]].copy()
        salidas.columns = ["Fecha", "Monto", "Referencia", "Responsable"]
        salidas["Tipo"] = "SALIDA"

        historial = pd.concat([entradas, salidas]).sort_values("Fecha", ascending=False)

        if not historial.empty:
            # Formatear
            historial["Monto"] = historial["Monto"].apply(formato_moneda)
            
            def color_tipo(val):
                color = 'green' if val == "ENTRADA" else 'red'
                return f'color: {color}; font-weight: bold'

            st.dataframe(
                historial[["Fecha", "Tipo", "Monto", "Referencia", "Responsable"]]
                .style.applymap(color_tipo, subset=["Tipo"]),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No hay movimientos registrados.")
