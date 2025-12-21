import streamlit as st
import pandas as pd
from datetime import datetime
import time
import uuid
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero, generar_id

# --- CONFIGURACIÓN ---
HOJA_CIERRES = "LOG_CIERRES_CAJA"
HOJA_RETIROS = "LOG_RETIROS_PROFIT"

HEADERS_RETIROS = ["ID", "Fecha", "Hora", "Monto", "Motivo", "Responsable"]

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

# --- BACKEND ---

def obtener_o_crear_hoja(sheet, nombre, headers):
    try: return sheet.worksheet(nombre)
    except:
        ws = sheet.add_worksheet(title=nombre, rows="1000", cols="10")
        ws.append_row(headers)
        return ws

def cargar_datos_banco(sheet):
    """Carga Cierres (Entradas) y Retiros (Salidas)."""
    try:
        # 1. Cierres (Fuente de Ingreso)
        ws_c = sheet.worksheet(HOJA_CIERRES)
        df_c = leer_datos_seguro(ws_c)
        if not df_c.empty:
            # Limpieza numérica agresiva
            if "Profit_Retenido" in df_c.columns:
                df_c["Profit_Num"] = df_c["Profit_Retenido"].astype(str).apply(limpiar_numero)
            else:
                df_c["Profit_Num"] = 0.0
                
            # Limpieza de estado
            if "Estado_Ahorro" not in df_c.columns:
                df_c["Estado_Ahorro"] = "PENDIENTE" # Asumir pendiente si no existe columna
        
        # 2. Retiros (Fuente de Egreso)
        ws_r = obtener_o_crear_hoja(sheet, HOJA_RETIROS, HEADERS_RETIROS)
        df_r = leer_datos_seguro(ws_r)
        if not df_r.empty:
            if "Monto" in df_r.columns:
                df_r["Monto_Num"] = df_r["Monto"].astype(str).apply(limpiar_numero)
            else:
                df_r["Monto_Num"] = 0.0
        
        return df_c, df_r, ws_c, ws_r

    except Exception as e:
        # st.error(f"Error cargando banco: {e}") 
        return pd.DataFrame(), pd.DataFrame(), None, None

def pagar_deuda_ahorro(ws_c, fecha_pago):
    """Busca el cierre por fecha y cambia PENDIENTE a GUARDADO."""
    try:
        fechas = ws_c.col_values(1) # Col A
        try:
            fila = fechas.index(str(fecha_pago)) + 1
        except: return False
        
        headers = ws_c.row_values(1)
        try: col = headers.index("Estado_Ahorro") + 1
        except: col = 10 # Fallback
        
        ws_c.update_cell(fila, col, "GUARDADO")
        return True
    except: return False

def registrar_retiro(ws_r, monto, motivo, responsable):
    try:
        f = datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d")
        h = datetime.now(ZONA_HORARIA).strftime("%H:%M")
        # ID, Fecha, Hora, Monto, Motivo, Resp
        ws_r.append_row([generar_id(), f, h, monto, motivo, responsable])
        return True
    except: return False

# --- INTERFAZ ---

def show(sheet):
    st.title("🐷 Banco de Ahorro (Profit First)")
    st.caption("Gestiona tu fondo de reservas, utilidades e inversión.")
    st.markdown("---")
    
    if not sheet: return

    with st.spinner("Conectando con el banco..."):
        df_c, df_r, ws_c, ws_r = cargar_datos_banco(sheet)

    if df_c.empty:
        st.info("No hay historial de cierres. Empieza a cerrar caja para generar ahorros.")
        return

    # --- 1. CÁLCULOS FINANCIEROS ---
    
    # Entradas: Suma de Profits con estado GUARDADO
    if "Estado_Ahorro" in df_c.columns:
        entradas_reales = df_c[df_c["Estado_Ahorro"] == "GUARDADO"]["Profit_Num"].sum()
        deuda_pendiente = df_c[df_c["Estado_Ahorro"] != "GUARDADO"]["Profit_Num"].sum() # Todo lo que no sea GUARDADO es deuda
    else:
        entradas_reales = 0
        deuda_pendiente = 0

    # Salidas: Suma de Retiros
    if not df_r.empty:
        salidas_reales = df_r["Monto_Num"].sum()
    else:
        salidas_reales = 0
        
    saldo_disponible = entradas_reales - salidas_reales

    # --- 2. DASHBOARD BANCARIO ---
    
    # Estilo visual de tarjetas
    k1, k2, k3 = st.columns(3)
    k1.metric("💰 Saldo Disponible", formato_moneda(saldo_disponible), help="Dinero real en la cuenta (Entradas - Salidas)")
    k2.metric("📥 Total Histórico Ahorrado", formato_moneda(entradas_reales))
    k3.metric("⚠️ Deuda por Transferir", formato_moneda(deuda_pendiente), delta_color="inverse", help="Dinero de ventas que aún no has pasado al banco.")

    st.markdown("---")

    tab_ingreso, tab_retiro, tab_ext = st.tabs(["🟠 INGRESAR (PAGAR DEUDA)", "💸 RETIRAR FONDOS", "📜 EXTRACTO"])

    # --- TAB 1: INGRESAR DINERO ---
    with tab_ingreso:
        st.subheader("Gestión de Pendientes")
        
        # Filtrar solo pendientes > 0
        df_pend = df_c[(df_c["Estado_Ahorro"] != "GUARDADO") & (df_c["Profit_Num"] > 0)].copy()
        
        if not df_pend.empty:
            st.info(f"Tienes **{len(df_pend)}** cierres sin transferir al fondo.")
            
            # Crear lista legible para el usuario
            df_pend["Etiqueta"] = df_pend.apply(lambda x: f"{x['Fecha']} | Monto: {formato_moneda(x['Profit_Num'])}", axis=1)
            
            opcion = st.selectbox("Selecciona el día a transferir:", df_pend["Etiqueta"].tolist())
            
            if st.button("✅ REGISTRAR TRANSFERENCIA", type="primary", use_container_width=True):
                fecha_pago = opcion.split(" | ")[0]
                monto_pago = df_pend[df_pend["Fecha"] == fecha_pago]["Profit_Num"].values[0]
                
                if pagar_deuda_ahorro(ws_c, fecha_pago):
                    st.balloons()
                    st.success(f"¡Excelente! Has sumado {formato_moneda(monto_pago)} a tu capital.")
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error("Error al actualizar la base de datos.")
        else:
            st.success("🎉 ¡Estás al día! No tienes deudas con tu fondo de ahorro.")

    # --- TAB 2: RETIRAR DINERO ---
    with tab_retiro:
        st.subheader("Retiro de Capital")
        st.caption("Registra salidas para inversión, repartición de utilidades o emergencias.")
        
        c_m, c_d = st.columns(2)
        monto_ret = c_m.number_input("Monto a Retirar ($)", min_value=0.0, step=50000.0)
        motivo = c_d.text_input("Motivo / Destino", placeholder="Ej: Compra de Nevera Nueva")
        resp = st.text_input("Autorizado por:", placeholder="Tu Nombre")
        
        if st.button("🚨 CONFIRMAR RETIRO", type="primary"):
            if monto_ret > 0 and motivo and resp:
                if monto_ret <= saldo_disponible:
                    if registrar_retiro(ws_r, monto_ret, motivo, resp):
                        st.success("✅ Retiro registrado exitosamente.")
                        st.cache_data.clear()
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("Error al guardar.")
                else:
                    st.error(f"❌ Fondos Insuficientes. Solo tienes {formato_moneda(saldo_disponible)}.")
            else:
                st.warning("Completa todos los campos.")

    # --- TAB 3: EXTRACTO DE MOVIMIENTOS ---
    with tab_ext:
        st.subheader("Movimientos Recientes")
        
        col_in, col_out = st.columns(2)
        
        with col_in:
            st.write("📥 **Últimos Aportes**")
            # Mostrar solo los guardados
            df_in_view = df_c[df_c["Estado_Ahorro"] == "GUARDADO"].copy()
            if not df_in_view.empty:
                df_in_view = df_in_view.sort_values("Fecha", ascending=False).head(10)
                df_in_view["Monto"] = df_in_view["Profit_Num"].apply(formato_moneda)
                st.dataframe(df_in_view[["Fecha", "Monto"]], use_container_width=True, hide_index=True)
            else:
                st.caption("Sin aportes registrados.")
                
        with col_out:
            st.write("📤 **Últimos Retiros**")
            if not df_r.empty:
                df_out_view = df_r.sort_values("Fecha", ascending=False).head(10)
                df_out_view["Monto"] = df_out_view["Monto_Num"].apply(formato_moneda)
                st.dataframe(df_out_view[["Fecha", "Monto", "Motivo"]], use_container_width=True, hide_index=True)
            else:
                st.caption("Sin retiros registrados.")
