import streamlit as st
import pandas as pd
from datetime import datetime, date
import time
import uuid
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero, generar_id

# --- CONFIGURACIÓN ---
HOJA_VENTAS = "LOG_VENTAS_LOYVERSE"
HOJA_GASTOS = "LOG_GASTOS"
HOJA_COMPRAS = "LOG_COMPRAS"
HOJA_CIERRES = "LOG_CIERRES_CAJA"
HOJA_RETIROS = "LOG_RETIROS_PROFIT"

# Encabezados Oficiales
HEADERS_CIERRE = [
    "Fecha", "Hora_Cierre", "Venta_Total_Bruta", "Venta_Efectivo", 
    "Gastos_Pagados_Efectivo", "Saldo_Teorico_Efectivo", "Saldo_Real_Contado", 
    "Diferencia", "Total_Nequi", "Total_Tarjetas", "Notas", 
    "Profit_Retenido", "Estado_Ahorro", "Numero_Cierre_Loyverse"
]

HEADERS_RETIROS = ["ID", "Fecha", "Hora", "Monto_Retirado", "Motivo", "Responsable"]

def formato_moneda_co(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

# --- FUNCIONES DE MANTENIMIENTO (AUTO-CREACIÓN) ---

def obtener_o_crear_hoja(sheet, nombre_hoja, headers_si_nuevo):
    """
    Intenta abrir la hoja. Si no existe, LA CREA DE UNA VEZ con los títulos.
    Devuelve el objeto worksheet listo para usar.
    """
    try:
        return sheet.worksheet(nombre_hoja)
    except:
        # Si falla, es que no existe. La creamos.
        ws = sheet.add_worksheet(title=nombre_hoja, rows="1000", cols="20")
        ws.append_row(headers_si_nuevo)
        return ws

def asegurar_columnas(ws, headers_oficiales):
    """Revisa si faltan columnas y las agrega."""
    try:
        current_headers = ws.row_values(1)
        if not current_headers:
            ws.append_row(headers_oficiales)
            return
        
        faltantes = [col for col in headers_oficiales if col not in current_headers]
        if faltantes:
            next_col = len(current_headers) + 1
            for col in faltantes:
                ws.update_cell(1, next_col, col)
                next_col += 1
    except: pass

# --- FUNCIONES DE DATOS ---

def cargar_datos_ahorro(sheet):
    """Carga datos garantizando que las hojas existan."""
    try:
        # 1. GARANTIZAR HOJA CIERRES
        ws_c = obtener_o_crear_hoja(sheet, HOJA_CIERRES, HEADERS_CIERRE)
        df_c = leer_datos_seguro(ws_c)
        
        # Limpieza de tipos
        if not df_c.empty:
            if "Profit_Retenido" in df_c.columns:
                df_c["Profit_Retenido"] = pd.to_numeric(df_c["Profit_Retenido"], errors='coerce').fillna(0)
        else:
            df_c = pd.DataFrame(columns=HEADERS_CIERRE)

        # 2. GARANTIZAR HOJA RETIROS (Aquí estaba el error antes)
        ws_r = obtener_o_crear_hoja(sheet, HOJA_RETIROS, HEADERS_RETIROS)
        df_r = leer_datos_seguro(ws_r)
        
        # Limpieza de tipos
        if not df_r.empty:
            if "Monto_Retirado" in df_r.columns:
                df_r["Monto_Retirado"] = pd.to_numeric(df_r["Monto_Retirado"], errors='coerce').fillna(0)
        else:
            df_r = pd.DataFrame(columns=HEADERS_RETIROS)

        return df_c, df_r
    except Exception as e:
        st.error(f"Error cargando ahorro: {e}")
        return pd.DataFrame(), pd.DataFrame()

def registrar_retiro_profit(sheet, monto, motivo, responsable):
    try:
        ws = obtener_o_crear_hoja(sheet, HOJA_RETIROS, HEADERS_RETIROS)
        
        fecha = datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d")
        hora = datetime.now(ZONA_HORARIA).strftime("%H:%M")
        
        ws.append_row([generar_id(), fecha, hora, monto, motivo, responsable])
        return True
    except Exception as e:
        st.error(f"Error registrando retiro: {e}")
        return False

def verificar_cierre_existente(sheet, fecha_str):
    try:
        ws = obtener_o_crear_hoja(sheet, HOJA_CIERRES, HEADERS_CIERRE)
        df = leer_datos_seguro(ws)
        if not df.empty and "Fecha" in df.columns:
            df["Fecha"] = df["Fecha"].astype(str)
            cierre = df[df["Fecha"] == fecha_str]
            if not cierre.empty: return cierre.iloc[0]
        return None
    except: return None

def cargar_historial_completo(sheet):
    try:
        ws = obtener_o_crear_hoja(sheet, HOJA_CIERRES, HEADERS_CIERRE)
        return leer_datos_seguro(ws)
    except: return pd.DataFrame()

def reabrir_caja(sheet, fecha_str):
    try:
        ws = sheet.worksheet(HOJA_CIERRES)
        data = ws.get_all_records()
        if not data: return True
        df = pd.DataFrame(data)
        df["Fecha"] = df["Fecha"].astype(str)
        df_limpio = df[df["Fecha"] != fecha_str]
        ws.clear()
        ws.update([df_limpio.columns.values.tolist()] + df_limpio.values.tolist())
        return True
    except: return False

def cargar_movimientos(sheet, fecha_str):
    try:
        # Ventas
        ws_ventas = sheet.worksheet(HOJA_VENTAS)
        df_ventas = pd.DataFrame(ws_ventas.get_all_records())
        if not df_ventas.empty:
            df_ventas["Fecha"] = df_ventas["Fecha"].astype(str)
            df_ventas = df_ventas[df_ventas["Fecha"] == fecha_str]
            df_ventas = df_ventas.drop_duplicates(subset=["Numero_Recibo", "ID_Plato", "Hora"])
            df_ventas["Total_Dinero"] = pd.to_numeric(df_ventas["Total_Dinero"], errors='coerce').fillna(0)
        
        # Gastos
        try:
            ws_g = sheet.worksheet(HOJA_GASTOS)
            df_g = leer_datos_seguro(ws_g)
            if not df_g.empty:
                df_g["Fecha"] = df_g["Fecha"].astype(str)
                df_g = df_g[df_g["Fecha"] == fecha_str]
                df_g["Monto"] = pd.to_numeric(df_g["Monto"], errors='coerce').fillna(0)
        except: df_g = pd.DataFrame()

        # Compras
        try:
            ws_c = sheet.worksheet(HOJA_COMPRAS)
            df_c = leer_datos_seguro(ws_c)
            if not df_c.empty:
                df_c["Fecha_Registro"] = df_c["Fecha_Registro"].astype(str)
                df_c = df_c[df_c["Fecha_Registro"] == fecha_str]
                df_c["Precio_Total_Pagado"] = pd.to_numeric(df_c["Precio_Total_Pagado"], errors='coerce').fillna(0)
        except: df_c = pd.DataFrame()

        return df_ventas, df_g, df_c, ws_ventas
    except: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), None

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

def guardar_cierre(sheet, datos_dict):
    try:
        ws = obtener_o_crear_hoja(sheet, HOJA_CIERRES, HEADERS_CIERRE)
        asegurar_columnas(ws, HEADERS_CIERRE)
        
        headers = ws.row_values(1)
        fila_ordenada = []
        for h in headers:
            val = datos_dict.get(h, "")
            if isinstance(val, (int, float)): fila_ordenada.append(float(val))
            else: fila_ordenada.append(str(val))
        ws.append_row(fila_ordenada)
        return True
    except Exception as e:
        st.error(f"Error guardando: {e}")
        return False

def pagar_ahorro_pendiente(sheet, fecha_pago):
    try:
        ws = sheet.worksheet(HOJA_CIERRES)
        fechas = ws.col_values(1)
        try: fila_index = fechas.index(str(fecha_pago)) + 1 
        except ValueError: return False 
        
        headers = ws.row_values(1)
        try: col_idx = headers.index("Estado_Ahorro") + 1
        except: col_idx = 10
        
        ws.update_cell(fila_index, col_idx, "GUARDADO")
        return True
    except: return False

# --- INTERFAZ ---
def show(sheet):
    st.title("🔐 Tesorería Central")
    st.markdown("---")
    
    if not sheet: return

    tab_caja, tab_ahorro = st.tabs(["📝 GESTIÓN DE CAJA", "🐷 BANCO DE AHORRO"])

    # TAB 1: CAJA
    with tab_caja:
        hoy = datetime.now(ZONA_HORARIA).date()
        col_f, col_s = st.columns([1, 2])
        fecha_cierre = col_f.date_input("Fecha de Arqueo", value=hoy)
        fecha_str = fecha_cierre.strftime("%Y-%m-%d")

        datos_cierre = verificar_cierre_existente(sheet, fecha_str)

        if datos_cierre is not None:
            # MODO LECTURA
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
            
            st.info(f"🐷 Ahorro del día: **{formato_moneda_co(profit)}** ({datos_cierre.get('Estado_Ahorro','-')})")
            st.text_area("Notas:", value=datos_cierre.get("Notas", ""), disabled=True)
            
            if st.button("🗑️ REABRIR CAJA", type="secondary"):
                if reabrir_caja(sheet, fecha_str): st.success("Reabierto."); time.sleep(1); st.rerun()
        else:
            # MODO EDICIÓN
            with col_s: st.warning("⚠️ **PENDIENTE**")
            df_ventas, df_g, df_c, ws_ventas = cargar_movimientos(sheet, fecha_str)

            v_total=0; v_efec=0; v_digi=0; v_tarj=0; g_efec=0; c_efec=0

            if df_ventas.empty:
                st.info("No hay ventas registradas hoy.")
            else:
                with st.expander("🛠️ Auditoría Pagos", expanded=False):
                    df_audit = df_ventas[["Hora", "Numero_Recibo", "Total_Dinero", "Metodo_Pago_Loyverse", "Metodo_Pago_Real_Auditado"]].drop_duplicates(subset=["Numero_Recibo"])
                    df_edit = st.data_editor(
                        df_audit,
                        column_config={"Metodo_Pago_Real_Auditado": st.column_config.SelectboxColumn("MÉTODO REAL", options=["Efectivo", "Nequi", "Tarjeta", "Rappi", "Otro"], required=True)},
                        hide_index=True, use_container_width=True
                    )
                    if st.button("💾 Guardar Correcciones"):
                        if actualizar_metodos_pago(ws_ventas, df_edit): st.success("Listo."); st.rerun()

                v_total = df_ventas["Total_Dinero"].sum()
                v_efec = df_ventas[df_ventas["Metodo_Pago_Real_Auditado"] == "Efectivo"]["Total_Dinero"].sum()
                v_digi = df_ventas[df_ventas["Metodo_Pago_Real_Auditado"].str.contains("Nequi|Davi|Banco|Transf", case=False, na=False)]["Total_Dinero"].sum()
                v_tarj = df_ventas[df_ventas["Metodo_Pago_Real_Auditado"].isin(["Tarjeta", "Datafono"])]["Total_Dinero"].sum()
                
                g_efec = df_g[df_g["Metodo_Pago"].str.contains("Efectivo", case=False)]["Monto"].sum() if not df_g.empty else 0
                c_efec = df_c[df_c["Metodo_Pago"].str.contains("Efectivo", case=False)]["Precio_Total_Pagado"].sum() if not df_c.empty else 0

            saldo_teorico = v_efec - g_efec - c_efec

            st.markdown("#### Resumen Financiero")
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("VENTA TOTAL", formato_moneda_co(v_total))
            k2.metric("Efectivo", formato_moneda_co(v_efec))
            k3.metric("Digital", formato_moneda_co(v_digi))
            k4.metric("Tarjetas", formato_moneda_co(v_tarj))
            
            st.markdown("---")
            c_p1, c_p2 = st.columns([1, 2])
            pct_prof = c_p1.number_input("% Ahorro", value=5, min_value=1)
            monto_p = v_total * (pct_prof/100)
            c_p2.info(f"👉 Ahorrar: **{formato_moneda_co(monto_p)}**")
            check_ahorro = c_p2.checkbox("✅ Confirmo transferencia")
            
            st.markdown("---")
            c1, c2, c3 = st.columns(3)
            c1.metric("(+) Entradas", formato_moneda_co(v_efec))
            c2.metric("(-) Salidas", formato_moneda_co(g_efec + c_efec))
            c3.metric("(=) TEÓRICO", formato_moneda_co(saldo_teorico))
            
            col_r, col_d = st.columns(2)
            real = col_r.number_input("¿Cuánto contaste?", min_value=0.0, step=500.0)
            diff = real - saldo_teorico
            
            with col_d:
                if diff == 0: st.success("✅ CUADRADO")
                elif diff > 0: st.info(f"🔵 SOBRA: {formato_moneda_co(diff)}")
                else: st.error(f"🔴 FALTA: {formato_moneda_co(diff)}")

            st.markdown("---")
            c_z, c_nota = st.columns([1, 2])
            num_z = c_z.text_input("🧾 N° Cierre Loyverse (Z)", placeholder="#1024")
            not_cierre = c_nota.text_area("Notas")
            
            if st.button("🔒 CERRAR CAJA", type="primary", use_container_width=True):
                est_ahorro = "GUARDADO" if check_ahorro else "PENDIENTE"
                datos_dict = {
                    "Fecha": fecha_str,
                    "Hora_Cierre": datetime.now(ZONA_HORARIA).strftime("%H:%M"),
                    "Venta_Total_Bruta": v_total, "Venta_Efectivo": v_efec,
                    "Gastos_Pagados_Efectivo": g_efec + c_efec,
                    "Saldo_Teorico_Efectivo": saldo_teorico, "Saldo_Real_Contado": real,
                    "Diferencia": diff, "Total_Nequi": v_digi, "Total_Tarjetas": v_tarj,
                    "Notas": not_cierre, "Profit_Retenido": monto_p, "Estado_Ahorro": est_ahorro,
                    "Numero_Cierre_Loyverse": str(num_z)
                }
                if guardar_cierre(sheet, datos_dict):
                    st.balloons(); st.success("Guardado."); st.cache_data.clear(); time.sleep(2); st.rerun()

        st.markdown("---")
        df_full = cargar_historial_completo(sheet)
        if not df_full.empty:
            st.caption("📜 Últimos cierres:")
            df_ver = df_full.head(5).copy()
            if "Numero_Cierre_Loyverse" not in df_ver.columns: df_ver["Numero_Cierre_Loyverse"] = "-"
            st.dataframe(df_ver[["Fecha", "Numero_Cierre_Loyverse", "Saldo_Real_Contado", "Diferencia", "Notas"]], use_container_width=True, hide_index=True)

    # TAB 2: AHORRO
    with tab_ahorro:
        st.subheader("🐷 Fondo de Reservas")
        df_c, df_r = cargar_datos_ahorro(sheet)
        
        if not df_c.empty:
            total_guardado = df_c[df_c["Estado_Ahorro"] == "GUARDADO"]["Profit_Retenido"].sum()
            total_retirado = df_r["Monto_Retirado"].sum() if not df_r.empty else 0
            saldo_banco = total_guardado - total_retirado
            total_deuda = df_c[df_c["Estado_Ahorro"] == "PENDIENTE"]["Profit_Retenido"].sum()
            
            k1, k2, k3 = st.columns(3)
            k1.metric("💰 Saldo Disponible", formato_moneda_co(saldo_banco))
            k2.metric("📥 Total Ahorrado", formato_moneda_co(total_guardado))
            k3.metric("⚠️ Deuda Pendiente", formato_moneda_co(total_deuda), delta_color="inverse")
            
            st.markdown("---")
            c_p, c_r = st.columns(2)
            
            with c_p:
                st.markdown("### 🟠 Pagar Pendientes")
                pendientes = df_c[df_c["Estado_Ahorro"] == "PENDIENTE"]
                if not pendientes.empty:
                    lista_pagar = pendientes.apply(lambda x: f"{x['Fecha']} - {formato_moneda_co(x['Profit_Retenido'])}", axis=1).tolist()
                    pago_sel = st.selectbox("Pagar:", lista_pagar)
                    if st.button("✅ YA HICE LA TRANSFERENCIA"):
                        if pagar_ahorro_pendiente(sheet, pago_sel.split(" - ")[0]):
                            st.success("Registrado."); st.cache_data.clear(); time.sleep(1); st.rerun()
                else: st.success("¡Al día!")

            with c_r:
                st.markdown("### 💸 Retirar Fondos")
                monto_ret = st.number_input("Monto a Retirar", min_value=0.0, step=50000.0)
                motivo = st.text_input("Motivo")
                resp = st.text_input("Responsable")
                if st.button("🚨 REGISTRAR RETIRO", type="primary"):
                    if monto_ret <= saldo_banco and monto_ret > 0:
                        if registrar_retiro_profit(sheet, monto_ret, motivo, resp):
                            st.success("Retiro OK."); st.cache_data.clear(); time.sleep(1); st.rerun()
                    else: st.error("Fondos insuficientes.")
            
            st.markdown("---")
            t1, t2 = st.tabs(["Entradas", "Salidas"])
            with t1: st.dataframe(df_c[["Fecha", "Profit_Retenido", "Estado_Ahorro"]].sort_values("Fecha", ascending=False), use_container_width=True)
            with t2: st.dataframe(df_r, use_container_width=True)
        else: st.info("Sin datos.")
