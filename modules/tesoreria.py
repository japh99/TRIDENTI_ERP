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
HOJA_RETIROS = "LOG_RETIROS_PROFIT"

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

# --- FUNCIONES DE BASE DE DATOS ---

def asegurar_columnas(ws):
    try:
        current = ws.row_values(1)
        if not current: ws.append_row(HEADERS_CIERRE); return
        faltantes = [c for c in HEADERS_CIERRE if c not in current]
        if faltantes:
            next_col = len(current) + 1
            for col in faltantes: ws.update_cell(1, next_col, col); next_col += 1
    except: pass

def obtener_o_crear_hoja(sheet, nombre, headers):
    try: return sheet.worksheet(nombre)
    except:
        ws = sheet.add_worksheet(title=nombre, rows="1000", cols="20")
        ws.append_row(headers)
        return ws

def guardar_cierre(sheet, datos_dict):
    try:
        ws = obtener_o_crear_hoja(sheet, HOJA_CIERRES, HEADERS_CIERRE)
        asegurar_columnas(ws)
        headers = ws.row_values(1)
        fila = []
        for h in headers:
            val = datos_dict.get(h, "")
            fila.append(float(val) if isinstance(val, (int, float)) else str(val))
        ws.append_row(fila)
        return True
    except Exception as e:
        st.error(f"Error guardando: {e}")
        return False

# --- FUNCIONES DE CORRECCIÓN (NUEVAS) ---

def corregir_monto_ahorro(sheet, fecha, nuevo_monto):
    """Permite editar un error en el historial de ahorros."""
    try:
        ws = sheet.worksheet(HOJA_CIERRES)
        # Buscar la fila por fecha
        col_fechas = ws.col_values(1)
        try:
            fila = col_fechas.index(str(fecha)) + 1
        except: return False
        
        # Buscar columna Profit
        headers = ws.row_values(1)
        try: col_idx = headers.index("Profit_Retenido") + 1
        except: return False
        
        ws.update_cell(fila, col_idx, float(nuevo_monto))
        return True
    except: return False

def cargar_movimientos(sheet, fecha_str):
    try:
        ws_v = sheet.worksheet(HOJA_VENTAS)
        df_v = pd.DataFrame(ws_v.get_all_records())
        if not df_v.empty:
            df_v["Fecha"] = df_v["Fecha"].astype(str)
            df_v = df_v[df_v["Fecha"] == fecha_str]
            df_v = df_v.drop_duplicates(subset=["Numero_Recibo", "ID_Plato", "Hora"])
            df_v["Total_Dinero"] = pd.to_numeric(df_v["Total_Dinero"], errors='coerce').fillna(0)
        
        try:
            ws_g = sheet.worksheet(HOJA_GASTOS)
            df_g = leer_datos_seguro(ws_g)
            if not df_g.empty:
                df_g["Fecha"] = df_g["Fecha"].astype(str)
                df_g = df_g[df_g["Fecha"] == fecha_str]
                df_g["Monto"] = pd.to_numeric(df_g["Monto"], errors='coerce').fillna(0)
        except: df_g = pd.DataFrame()

        try:
            ws_c = sheet.worksheet(HOJA_COMPRAS)
            df_c = leer_datos_seguro(ws_c)
            if not df_c.empty:
                df_c["Fecha_Registro"] = df_c["Fecha_Registro"].astype(str)
                df_c = df_c[df_c["Fecha_Registro"] == fecha_str]
                df_c["Precio_Total_Pagado"] = pd.to_numeric(df_c["Precio_Total_Pagado"], errors='coerce').fillna(0)
        except: df_c = pd.DataFrame()

        return df_v, df_g, df_c
    except: return None, None, None

def cargar_datos_ahorro(sheet):
    try:
        ws_c = obtener_o_crear_hoja(sheet, HOJA_CIERRES, HEADERS_CIERRE)
        df_c = leer_datos_seguro(ws_c)
        if not df_c.empty:
            if "Profit_Retenido" in df_c.columns:
                # Limpieza fuerte para quitar $ y ,
                df_c["Profit_Num"] = df_c["Profit_Retenido"].astype(str).apply(limpiar_numero)
            else: df_c["Profit_Num"] = 0.0

        ws_r = obtener_o_crear_hoja(sheet, HOJA_RETIROS, HEADERS_RETIROS)
        df_r = leer_datos_seguro(ws_r)
        if not df_r.empty:
            if "Monto_Retirado" in df_r.columns:
                df_r["Monto_Num"] = df_r["Monto_Retirado"].astype(str).apply(limpiar_numero)
            else: df_r["Monto_Num"] = 0.0
            
        return df_c, df_r
    except: return pd.DataFrame(), pd.DataFrame()

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
        df = pd.DataFrame(data)
        df["Fecha"] = df["Fecha"].astype(str)
        df_new = df[df["Fecha"] != fecha_str]
        ws.clear()
        ws.update([df_new.columns.values.tolist()] + df_new.values.tolist())
        return True
    except: return False

def registrar_retiro_profit(sheet, monto, motivo, responsable):
    try:
        ws = obtener_o_crear_hoja(sheet, HOJA_RETIROS, HEADERS_RETIROS)
        fecha = datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d")
        hora = datetime.now(ZONA_HORARIA).strftime("%H:%M")
        ws.append_row([generar_id(), fecha, hora, monto, motivo, responsable])
        return True
    except: return False

def pagar_ahorro_pendiente(sheet, fecha_pago):
    try:
        ws = sheet.worksheet(HOJA_CIERRES)
        fechas = ws.col_values(1)
        idx = fechas.index(str(fecha_pago)) + 1 
        headers = ws.row_values(1)
        try: c_idx = headers.index("Estado_Ahorro") + 1
        except: c_idx = 10
        ws.update_cell(idx, c_idx, "GUARDADO")
        return True
    except: return False

def actualizar_metodos_pago(sheet, df_editado):
    try:
        ws = sheet.worksheet(HOJA_VENTAS)
        col_recibos = ws.col_values(3)
        for index, row in df_editado.iterrows():
            recibo = str(row["Numero_Recibo"])
            nuevo = row["Metodo_Pago_Real_Auditado"]
            orig = row["Metodo_Pago_Loyverse"]
            if nuevo != orig:
                try:
                    fila = col_recibos.index(recibo) + 1 
                    ws.update_cell(fila, 9, nuevo)
                except: pass
        return True
    except: return False

# --- INTERFAZ ---

def show(sheet):
    st.title("🔐 Tesorería Central")
    st.markdown("---")
    if not sheet: return

    tab_caja, tab_ahorro = st.tabs(["📝 GESTIÓN DE CAJA", "🐷 BANCO DE AHORRO"])

    # TAB 1: GESTIÓN DE CAJA
    with tab_caja:
        hoy = datetime.now(ZONA_HORARIA).date()
        c_f, c_s = st.columns([1, 2])
        fecha_cierre = c_f.date_input("Fecha", value=hoy)
        fecha_str = fecha_cierre.strftime("%Y-%m-%d")

        datos_cierre = verificar_cierre_existente(sheet, fecha_str)

        if datos_cierre is not None:
            # MODO LECTURA
            z = datos_cierre.get("Numero_Cierre_Loyverse", "S/N")
            with c_s: st.success(f"✅ **DÍA CERRADO** (Z: {z})")
            
            # Datos
            teorico = float(limpiar_numero(datos_cierre.get("Saldo_Teorico_Efectivo", 0)))
            real = float(limpiar_numero(datos_cierre.get("Saldo_Real_Contado", 0)))
            diff = float(limpiar_numero(datos_cierre.get("Diferencia", 0)))
            profit = float(limpiar_numero(datos_cierre.get("Profit_Retenido", 0)))
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Debía Haber", formato_moneda_co(teorico))
            c2.metric("Se Contó", formato_moneda_co(real))
            c3.metric("Diferencia", formato_moneda_co(diff), delta_color="off")
            
            st.info(f"🐷 Ahorro registrado: **{formato_moneda_co(profit)}**")
            
            if st.button("🗑️ REABRIR CAJA", type="secondary"):
                if reabrir_caja(sheet, fecha_str): 
                    st.success("Reabierto."); time.sleep(1); st.rerun()
        else:
            # MODO EDICIÓN
            with c_s: st.warning("⚠️ **PENDIENTE**")
            
            df_ventas, df_g, df_c = cargar_movimientos(sheet, fecha_str)

            v_tot=0; v_ef=0; v_dig=0; v_tar=0; g_ef=0; c_ef=0

            if df_ventas is not None and not df_ventas.empty:
                # Auditoría
                with st.expander("🛠️ Auditoría Pagos (Corregir)", expanded=False):
                    df_audit = df_ventas[["Hora", "Numero_Recibo", "Total_Dinero", "Metodo_Pago_Loyverse", "Metodo_Pago_Real_Auditado"]].drop_duplicates(subset=["Numero_Recibo"])
                    df_edit = st.data_editor(
                        df_audit,
                        column_config={"Metodo_Pago_Real_Auditado": st.column_config.SelectboxColumn("MÉTODO REAL", options=["Efectivo", "Nequi", "Tarjeta", "Rappi", "Otro"], required=True)},
                        hide_index=True, use_container_width=True
                    )
                    if st.button("💾 Guardar Correcciones"):
                        if actualizar_metodos_pago(sheet, df_edit): st.success("Listo."); st.rerun()

                v_tot = df_ventas["Total_Dinero"].sum()
                v_ef = df_ventas[df_ventas["Metodo_Pago_Real_Auditado"] == "Efectivo"]["Total_Dinero"].sum()
                v_dig = df_ventas[df_ventas["Metodo_Pago_Real_Auditado"].str.contains("Nequi|Davi|Banco|Transf", case=False, na=False)]["Total_Dinero"].sum()
                v_tar = df_ventas[df_ventas["Metodo_Pago_Real_Auditado"].isin(["Tarjeta", "Datafono"])]["Total_Dinero"].sum()
                
                g_ef = df_g[df_g["Metodo_Pago"].str.contains("Efectivo", case=False)]["Monto"].sum() if not df_g.empty else 0
                c_ef = df_c[df_c["Metodo_Pago"].str.contains("Efectivo", case=False)]["Precio_Total_Pagado"].sum() if not df_c.empty else 0

            saldo_teo = v_ef - g_ef - c_ef

            # Resumen
            st.markdown("#### Resumen Financiero")
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("VENTA TOTAL", formato_moneda_co(v_tot))
            k2.metric("Efectivo", formato_moneda_co(v_ef))
            k3.metric("Digital", formato_moneda_co(v_dig))
            k4.metric("Tarjetas", formato_moneda_co(v_tar))
            
            st.markdown("---")
            
            # --- PROFIT FIRST CORREGIDO ---
            st.subheader("💰 Fondo de Ahorro")
            usar_profit = st.checkbox("¿Aplicar ahorro hoy?", value=True)
            monto_final_ahorro = 0.0
            
            if usar_profit:
                c_p1, c_p2 = st.columns([1, 2])
                pct_prof = c_p1.number_input("% Ahorro", value=5, min_value=1)
                sugerido = v_tot * (pct_prof/100)
                
                with c_p2:
                    # ESTE ES EL CAMPO QUE SE GUARDARÁ
                    monto_final_ahorro = st.number_input("Monto a Ahorrar (Editable)", value=float(sugerido), step=1000.0)
                    estado_ahorro_sel = st.radio("Estado:", ["🔴 PENDIENTE", "🟢 GUARDADO"], horizontal=True)
            else:
                estado_ahorro_sel = "🔴 PENDIENTE" # Default

            st.markdown("---")
            # Arqueo
            c1, c2, c3 = st.columns(3)
            c1.metric("(+) Entradas", formato_moneda_co(v_ef))
            c2.metric("(-) Salidas", formato_moneda_co(g_ef + c_ef))
            c3.metric("(=) TEÓRICO", formato_moneda_co(saldo_teo))
            
            cr, cd = st.columns(2)
            real = cr.number_input("¿Cuánto contaste?", min_value=0.0, step=500.0)
            diff = real - saldo_teo
            
            with cd:
                if diff == 0: st.success("✅ CUADRADO")
                else: st.error(f"🔴 FALTA: {formato_moneda_co(diff)}") if diff < 0 else st.info(f"🔵 SOBRA: {formato_moneda_co(diff)}")

            c_z, c_note = st.columns([1, 2])
            num_z = c_z.text_input("🧾 Z-Report", placeholder="#1025")
            not_cierre = c_note.text_area("Notas")
            
            if st.button("🔒 CERRAR CAJA", type="primary", use_container_width=True):
                est_final = "GUARDADO" if "🟢" in estado_ahorro_sel else "PENDIENTE"
                # Si el monto es 0, no hay estado
                if monto_final_ahorro == 0: est_final = "N/A"

                datos = {
                    "Fecha": fecha_str,
                    "Hora_Cierre": datetime.now(ZONA_HORARIA).strftime("%H:%M"),
                    "Venta_Total_Bruta": v_tot, "Venta_Efectivo": v_ef,
                    "Gastos_Pagados_Efectivo": g_ef + c_ef,
                    "Saldo_Teorico_Efectivo": saldo_teo, "Saldo_Real_Contado": real,
                    "Diferencia": diff, "Total_Nequi": v_dig, "Total_Tarjetas": v_tar,
                    "Notas": not_cierre, 
                    "Profit_Retenido": monto_final_ahorro, # AQUÍ ESTÁ LA CORRECCIÓN
                    "Estado_Ahorro": est_final,
                    "Numero_Cierre_Loyverse": str(num_z)
                }
                if guardar_cierre(sheet, datos):
                    st.balloons(); st.success("Guardado."); st.cache_data.clear(); time.sleep(2); st.rerun()

    # TAB 2: AHORRO
    with tab_ahorro:
        st.subheader("🐷 Banco de Ahorro")
        df_c, df_r = cargar_datos_ahorro(sheet)
        
        if not df_c.empty:
            total_guardado = df_c[df_c["Estado_Ahorro"] == "GUARDADO"]["Profit_Num"].sum()
            total_retirado = df_r["Monto_Num"].sum() if not df_r.empty else 0
            saldo_banco = total_guardado - total_retirado
            total_deuda = df_c[df_c["Estado_Ahorro"] == "PENDIENTE"]["Profit_Num"].sum()
            
            k1, k2, k3 = st.columns(3)
            k1.metric("💰 Saldo Disponible", formato_moneda_co(saldo_banco))
            k2.metric("📥 Histórico Guardado", formato_moneda_co(total_guardado))
            k3.metric("⚠️ Deuda", formato_moneda_co(total_deuda), delta_color="inverse")
            
            # --- HERRAMIENTA DE CORRECCIÓN (NUEVA) ---
            with st.expander("🛠️ Corregir monto de un día pasado"):
                lista_fechas = df_c["Fecha"].tolist()
                f_sel = st.selectbox("Fecha:", lista_fechas)
                val_actual = df_c[df_c["Fecha"] == f_sel].iloc[0]["Profit_Num"]
                
                c_edit1, c_edit2 = st.columns(2)
                nuevo_m = c_edit1.number_input("Monto Correcto:", value=float(val_actual), step=1000.0)
                if c_edit2.button("💾 Actualizar Monto"):
                    if corregir_monto_ahorro(sheet, f_sel, nuevo_m):
                        st.success("Corregido."); st.cache_data.clear(); time.sleep(1); st.rerun()

            # PAGAR DEUDA
            pendientes = df_c[df_c["Estado_Ahorro"] == "PENDIENTE"]
            if not pendientes.empty:
                st.markdown("---")
                st.write("### 🟠 Pagar Pendientes")
                ops = pendientes.apply(lambda x: f"{x['Fecha']} - {formato_moneda_co(x['Profit_Num'])}", axis=1).tolist()
                pay = st.selectbox("Pagar:", ops)
                if st.button("✅ REGISTRAR TRANSFERENCIA"):
                    if pagar_ahorro_pendiente(sheet, pay.split(" - ")[0]):
                        st.success("Listo."); st.cache_data.clear(); time.sleep(1); st.rerun()

            # RETIROS
            st.markdown("---")
            st.write("### 💸 Retirar")
            c_m, c_d = st.columns(2)
            m_ret = c_m.number_input("Monto", min_value=0.0, step=50000.0)
            mot = c_d.text_input("Motivo")
            resp = c_d.text_input("Responsable")
            
            if st.button("🚨 RETIRAR", type="primary"):
                if m_ret <= saldo_banco and m_ret > 0:
                    if registrar_retiro_profit(sheet, m_ret, mot, resp):
                        st.success("Retiro OK."); st.cache_data.clear(); time.sleep(1); st.rerun()
                else: st.error("Fondos insuficientes.")

            # TABLAS
            st.markdown("---")
            t1, t2 = st.tabs(["Entradas", "Salidas"])
            with t1: st.dataframe(df_c[["Fecha", "Profit_Retenido", "Estado_Ahorro"]].sort_values("Fecha", ascending=False), use_container_width=True)
            with t2: st.dataframe(df_r, use_container_width=True) if not df_r.empty else st.info("Sin retiros.")
        else: st.info("Sin datos.")
