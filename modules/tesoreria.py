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

# Encabezados oficiales (Son 14 columnas)
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

# --- FUNCIONES DE MANTENIMIENTO DB (EL ARREGLO) ---

def asegurar_columnas(ws):
    """
    Ensancha la hoja si es muy pequeña y pone los títulos.
    """
    try:
        # 1. AMPLIAR LA HOJA SI ES NECESARIO
        # Si tiene menos de 15 columnas, la obligamos a crecer
        if ws.col_count < 15:
            ws.resize(cols=15)
            time.sleep(1) # Pausa técnica para que Google procese

        # 2. PONER ENCABEZADOS
        current_headers = ws.row_values(1)
        if not current_headers:
            ws.insert_row(HEADERS_CIERRE, 1)
            return

        # 3. RELLENAR HUECOS
        # Recorremos la lista oficial y si falta alguno en la fila 1, lo escribimos
        for i, col_name in enumerate(HEADERS_CIERRE):
            # i + 1 porque Excel empieza en 1
            if i >= len(current_headers) or current_headers[i] != col_name:
                ws.update_cell(1, i + 1, col_name)
                
    except Exception as e:
        # No bloqueamos el flujo, solo avisamos en consola
        print(f"Aviso de estructura: {e}")

def obtener_o_crear_hoja(sheet, nombre, headers):
    try: return sheet.worksheet(nombre)
    except:
        ws = sheet.add_worksheet(title=nombre, rows="1000", cols="20")
        ws.append_row(headers)
        return ws

def guardar_cierre(sheet, datos_dict):
    try:
        ws = obtener_o_crear_hoja(sheet, HOJA_CIERRES, HEADERS_CIERRE)
        
        # Paso Clave: Asegurar espacio antes de escribir
        asegurar_columnas(ws)
        
        # Mapeo de datos ordenados
        fila_ordenada = []
        for h in HEADERS_CIERRE:
            val = datos_dict.get(h, "")
            if isinstance(val, (int, float)): fila_ordenada.append(float(val))
            else: fila_ordenada.append(str(val))
            
        ws.append_row(fila_ordenada)
        return True
    except Exception as e:
        st.error(f"Error guardando: {e}")
        return False

# --- RESTO DE FUNCIONES (Iguales, pero necesarias para que corra) ---

def registrar_retiro_profit(sheet, monto, motivo, responsable):
    try:
        ws = obtener_o_crear_hoja(sheet, HOJA_RETIROS, HEADERS_RETIROS)
        fecha = datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d")
        hora = datetime.now(ZONA_HORARIA).strftime("%H:%M")
        ws.append_row([generar_id(), fecha, hora, monto, motivo, responsable])
        return True
    except: return False

def cargar_datos_ahorro(sheet):
    try:
        ws_c = obtener_o_crear_hoja(sheet, HOJA_CIERRES, HEADERS_CIERRE)
        df_c = leer_datos_seguro(ws_c)
        if not df_c.empty:
            if "Profit_Retenido" in df_c.columns:
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
        if not data: return True
        df = pd.DataFrame(data)
        df["Fecha"] = df["Fecha"].astype(str)
        df_new = df[df["Fecha"] != fecha_str]
        ws.clear()
        ws.update([df_new.columns.values.tolist()] + df_new.values.tolist())
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

        return df_v, df_g, df_c, ws_v
    except: return None, None, None, None

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

def pagar_ahorro_pendiente(sheet, fecha_pago):
    try:
        ws = sheet.worksheet(HOJA_CIERRES)
        fechas = ws.col_values(1)
        try: idx = fechas.index(str(fecha_pago)) + 1 
        except: return False
        
        headers = ws.row_values(1)
        try: c_idx = headers.index("Estado_Ahorro") + 1
        except: c_idx = 10 # Default si no encuentra header
        
        ws.update_cell(idx, c_idx, "GUARDADO")
        return True
    except: return False

def corregir_monto_ahorro(sheet, fecha, nuevo_monto):
    try:
        ws = sheet.worksheet(HOJA_CIERRES)
        fechas = ws.col_values(1)
        try: fila = fechas.index(str(fecha)) + 1
        except: return False
        headers = ws.row_values(1)
        try: col = headers.index("Profit_Retenido") + 1
        except: return False
        ws.update_cell(fila, col, float(nuevo_monto))
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
            z = datos_cierre.get("Numero_Cierre_Loyverse", "S/N")
            with col_s: st.success(f"✅ **DÍA CERRADO** (Z-Report: #{z})")
            
            teorico = float(limpiar_numero(datos_cierre.get("Saldo_Teorico_Efectivo", 0)))
            real = float(limpiar_numero(datos_cierre.get("Saldo_Real_Contado", 0)))
            diff = float(limpiar_numero(datos_cierre.get("Diferencia", 0)))
            profit = float(limpiar_numero(datos_cierre.get("Profit_Retenido", 0)))
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Debía Haber", formato_moneda_co(teorico))
            c2.metric("Se Contó", formato_moneda_co(real))
            c3.metric("Diferencia", formato_moneda_co(diff), delta_color="off")
            
            st.info(f"🐷 Ahorro: **{formato_moneda_co(profit)}** ({datos_cierre.get('Estado_Ahorro','-')})")
            st.text_area("Notas:", value=datos_cierre.get("Notas", ""), disabled=True)
            
            if st.button("🗑️ REABRIR CAJA", type="secondary"):
                if reabrir_caja(sheet, fecha_str): st.success("Reabierto."); time.sleep(1); st.rerun()

        else:
            with col_s: st.warning("⚠️ **PENDIENTE**")
            df_ventas, df_g, df_c, ws_ventas = cargar_movimientos(sheet, fecha_str)

            v_total=0; v_efec=0; v_digi=0; v_tarj=0; g_efec=0; c_efec=0

            if df_ventas is not None and not df_ventas.empty:
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
            st.subheader("💰 Fondo de Ahorro")
            usar_profit = st.checkbox("¿Aplicar ahorro?", value=True)
            monto_p_real = 0.0
            
            if usar_profit:
                c_p1, c_p2 = st.columns([1, 2])
                pct_prof = c_p1.number_input("% Ahorro", value=5, min_value=1)
                sugerido = v_total * (pct_prof/100)
                with c_p2:
                    monto_p_real = st.number_input("Monto a Ahorrar (Editable)", value=float(sugerido), step=1000.0)
                    estado_ahorro_sel = st.radio("Estado:", ["🔴 PENDIENTE", "🟢 GUARDADO"], horizontal=True)
            else:
                estado_ahorro_sel = "🔴 PENDIENTE"

            st.markdown("---")
            st.subheader("💵 Arqueo de Efectivo")
            c1, c2, c3 = st.columns(3)
            c1.metric("(+) Entradas", formato_moneda_co(v_efec))
            c2.metric("(-) Salidas", formato_moneda_co(g_efec + c_efec))
            c3.metric("(=) TEÓRICO", formato_moneda_co(saldo_teorico))
            
            col_r, col_d = st.columns(2)
            real = col_r.number_input("¿Cuánto contaste?", min_value=0.0, step=500.0)
            diff = real - saldo_teorico
            
            with col_d:
                if diff == 0: st.success("✅ CUADRADO")
                else: st.error(f"🔴 FALTA: {formato_moneda_co(diff)}") if diff < 0 else st.info(f"🔵 SOBRA: {formato_moneda_co(diff)}")

            c_z, c_nota = st.columns([1, 2])
            num_z = c_z.text_input("🧾 Z-Report", placeholder="#1025")
            not_cierre = c_nota.text_area("Notas")
            
            if st.button("🔒 CERRAR CAJA", type="primary", use_container_width=True):
                est_final = "GUARDADO" if "🟢" in estado_ahorro_sel else "PENDIENTE"
                if monto_p_real == 0: est_final = "N/A"

                datos_dict = {
                    "Fecha": fecha_str,
                    "Hora_Cierre": datetime.now(ZONA_HORARIA).strftime("%H:%M"),
                    "Venta_Total_Bruta": v_total, "Venta_Efectivo": v_efec,
                    "Gastos_Pagados_Efectivo": g_efec + c_efec,
                    "Saldo_Teorico_Efectivo": saldo_teorico, "Saldo_Real_Contado": real,
                    "Diferencia": diff, "Total_Nequi": v_digi, "Total_Tarjetas": v_tarj,
                    "Notas": not_cierre, "Profit_Retenido": monto_p_real, "Estado_Ahorro": est_final,
                    "Numero_Cierre_Loyverse": str(num_z)
                }
                if guardar_cierre(sheet, datos_dict):
                    st.balloons(); st.success("Guardado."); st.cache_data.clear(); time.sleep(2); st.rerun()

        st.markdown("---")
        st.subheader("📜 Historial")
        df_full = cargar_historial_completo(sheet)
        if not df_full.empty:
            df_ver = df_full.copy()
            if "Numero_Cierre_Loyverse" not in df_ver.columns: df_ver["Numero_Cierre_Loyverse"] = "-"
            for col in ["Saldo_Real_Contado", "Diferencia", "Profit_Retenido"]:
                if col in df_ver.columns:
                    df_ver[col] = pd.to_numeric(df_ver[col], errors='coerce').apply(formato_moneda_co)
            st.dataframe(df_ver[["Fecha", "Numero_Cierre_Loyverse", "Saldo_Real_Contado", "Diferencia", "Profit_Retenido", "Estado_Ahorro"]].sort_values("Fecha", ascending=False), use_container_width=True, hide_index=True)

    # TAB 2: AHORRO
    with tab_ahorro:
        st.subheader("🐷 Fondo de Reservas")
        df_c, df_r = cargar_datos_ahorro(sheet)
        
        if not df_c.empty:
            guardados = df_c[df_c["Estado_Ahorro"] == "GUARDADO"]["Profit_Num"].sum()
            pendientes = df_c[df_c["Estado_Ahorro"] == "PENDIENTE"]["Profit_Num"].sum()
            retirados = df_r["Monto_Num"].sum() if not df_r.empty else 0
            saldo_banco = guardados - retirados
            
            k1, k2, k3 = st.columns(3)
            k1.metric("💰 Saldo Disponible", formato_moneda_co(saldo_banco))
            k2.metric("📥 Total Ahorrado", formato_moneda_co(guardados))
            k3.metric("⚠️ Pendiente", formato_moneda_co(pendientes), delta_color="inverse")
            
            with st.expander("🛠️ Corregir monto histórico"):
                f_sel = st.selectbox("Fecha:", df_c["Fecha"].tolist())
                if st.button("Buscar valor"):
                    st.write(f"Valor actual: {df_c[df_c['Fecha']==f_sel]['Profit_Num'].values[0]}")
                nm = st.number_input("Nuevo Monto", step=1000.0)
                if st.button("Actualizar Monto"):
                    if corregir_monto_ahorro(sheet, f_sel, nm): st.success("Ok"); st.cache_data.clear(); st.rerun()

            if not pendientes.empty:
                st.markdown("### 🟠 Pagar Pendientes")
                ops = pd.DataFrame({'Fecha': pendientes['Fecha'], 'Monto': pendientes['Profit_Num']})
                ops['Label'] = ops.apply(lambda x: f"{x['Fecha']} - {formato_moneda_co(x['Monto'])}", axis=1)
                pago = st.selectbox("Pagar:", ops['Label'].tolist())
                if st.button("✅ REGISTRAR PAGO"):
                    if pagar_ahorro_pendiente(sheet, pago.split(" - ")[0]):
                        st.success("Listo."); st.cache_data.clear(); time.sleep(1); st.rerun()
            
            st.markdown("---")
            st.write("### 💸 Retirar")
            c_ret1, c_ret2 = st.columns(2)
            m_ret = c_ret1.number_input("Monto", step=50000.0)
            mot = c_ret2.text_input("Motivo")
            resp = c_ret2.text_input("Responsable")
            if st.button("🚨 RETIRAR", type="primary"):
                if m_ret <= saldo_banco and m_ret > 0:
                    if registrar_retiro_profit(sheet, m_ret, mot, resp):
                        st.success("Retiro OK."); st.cache_data.clear(); time.sleep(1); st.rerun()
                else: st.error("Fondos insuficientes.")
            
            st.markdown("---")
            t1, t2 = st.tabs(["Entradas", "Salidas"])
            with t1: st.dataframe(df_c[["Fecha", "Profit_Retenido", "Estado_Ahorro"]].sort_values("Fecha", ascending=False), use_container_width=True)
            with t2: st.dataframe(df_r, use_container_width=True)
        else: st.info("Sin datos.")
