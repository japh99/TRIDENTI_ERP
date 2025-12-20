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

# --- NUEVA ESTRUCTURA COMPLETA ---
HEADERS_CIERRE = [
    "Fecha", "Hora_Cierre", 
    "Venta_Total_Bruta",       # NUEVO: Cuánto se vendió en total
    "Venta_Efectivo",          # NUEVO: Cuánto entró en efectivo
    "Gastos_Pagados_Efectivo", # NUEVO: Cuánto salió en efectivo
    "Saldo_Teorico_Efectivo",  # (Venta Efec - Gastos Efec)
    "Saldo_Real_Contado", 
    "Diferencia", 
    "Total_Nequi", "Total_Tarjetas", 
    "Notas", "Profit_Retenido", "Estado_Ahorro", "Numero_Cierre_Loyverse"
]

def formato_moneda_co(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

# --- FUNCIONES DE CARGA Y MANTENIMIENTO ---

def asegurar_columnas(ws):
    """Crea las columnas que falten en el Excel automáticamente."""
    try:
        current_headers = ws.row_values(1)
        if not current_headers:
            ws.append_row(HEADERS_CIERRE)
            return
        
        # Buscar qué falta
        faltantes = [col for col in HEADERS_CIERRE if col not in current_headers]
        
        if faltantes:
            next_col = len(current_headers) + 1
            for col in faltantes:
                ws.update_cell(1, next_col, col)
                next_col += 1
    except: pass

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

def cargar_historial_completo(sheet):
    try:
        ws = sheet.worksheet(HOJA_CIERRES)
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
        # 1. Ventas
        ws_ventas = sheet.worksheet(HOJA_VENTAS)
        data_v = ws_ventas.get_all_records()
        df_ventas = pd.DataFrame(data_v)
        if not df_ventas.empty:
            df_ventas["Fecha"] = df_ventas["Fecha"].astype(str)
            df_ventas = df_ventas[df_ventas["Fecha"] == fecha_str]
            df_ventas["Total_Dinero"] = pd.to_numeric(df_ventas["Total_Dinero"], errors='coerce').fillna(0)
        
        # 2. Gastos
        try:
            ws_g = sheet.worksheet(HOJA_GASTOS)
            df_g = leer_datos_seguro(ws_g)
            if not df_g.empty:
                df_g["Fecha"] = df_g["Fecha"].astype(str)
                df_g = df_g[df_g["Fecha"] == fecha_str]
                df_g["Monto"] = pd.to_numeric(df_g["Monto"], errors='coerce').fillna(0)
        except: df_g = pd.DataFrame()

        # 3. Compras
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

def guardar_cierre_completo(sheet, datos_dict):
    """Guarda mapeando cada valor a su columna correcta, sin importar el orden."""
    try:
        try:
            ws = sheet.worksheet(HOJA_CIERRES)
        except:
            ws = sheet.add_worksheet(title=HOJA_CIERRES, rows="1000", cols="15")
        
        # 1. Asegurar columnas
        asegurar_estructura_db(ws)
        
        # 2. Leer headers actuales para saber el orden
        headers = ws.row_values(1)
        
        # 3. Construir la fila ordenada
        fila_a_guardar = []
        for h in headers:
            # Busca el valor en el diccionario, si no está, pone vacío
            val = datos_dict.get(h, "")
            # Convertir a float si es numérico para evitar error JSON
            if isinstance(val, (int, float)):
                fila_a_guardar.append(float(val))
            else:
                fila_a_guardar.append(str(val))
        
        ws.append_row(fila_a_guardar)
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

    # TAB 1
    with tab_caja:
        hoy = datetime.now(ZONA_HORARIA).date()
        col_f, col_s = st.columns([1, 2])
        fecha_cierre = col_f.date_input("Fecha de Arqueo", value=hoy)
        fecha_str = fecha_cierre.strftime("%Y-%m-%d")

        datos_cierre = verificar_cierre_existente(sheet, fecha_str)

        if datos_cierre is not None:
            # LECTURA
            z = datos_cierre.get("Numero_Cierre_Loyverse", "-")
            with col_s: st.success(f"✅ **CERRADO** (Z: {z})")
            
            # Recuperar datos seguros
            def get_val(k): return float(limpiar_numero(datos_cierre.get(k, 0)))
            
            teorico = get_val("Saldo_Teorico_Efectivo")
            real = get_val("Saldo_Real_Contado")
            diff = get_val("Diferencia")
            
            # Mostrar datos nuevos si existen
            v_bruta = get_val("Venta_Total_Bruta")
            v_efec = get_val("Venta_Efectivo")
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Debía Haber", formato_moneda_co(teorico))
            c2.metric("Se Contó", formato_moneda_co(real))
            c3.metric("Diferencia", formato_moneda_co(diff), delta_color="off")
            
            if v_bruta > 0:
                st.caption(f"📊 Venta Total: {formato_moneda_co(v_bruta)} | Efectivo: {formato_moneda_co(v_efec)}")
            
            st.text_area("Notas:", value=datos_cierre.get("Notas", ""), disabled=True)
            
            if st.button("🗑️ REABRIR CAJA", type="secondary"):
                if reabrir_caja(sheet, fecha_str): st.success("Reabierto."); time.sleep(1); st.rerun()
        else:
            # EDICIÓN
            with col_s: st.warning("⚠️ **PENDIENTE**")
            df_ventas, df_gastos, df_compras, ws_ventas = cargar_movimientos(sheet, fecha_str)

            if df_ventas is None or df_ventas.empty:
                st.error("Descarga ventas primero.")
            else:
                # AUDITORÍA
                with st.expander("🛠️ Auditoría Pagos", expanded=False):
                    df_audit = df_ventas[["Hora", "Numero_Recibo", "Total_Dinero", "Metodo_Pago_Loyverse", "Metodo_Pago_Real_Auditado"]].drop_duplicates(subset=["Numero_Recibo"])
                    df_edit = st.data_editor(
                        df_audit,
                        column_config={"Metodo_Pago_Real_Auditado": st.column_config.SelectboxColumn("MÉTODO REAL", options=["Efectivo", "Nequi", "Tarjeta", "Rappi", "Otro"], required=True)},
                        hide_index=True, use_container_width=True
                    )
                    if st.button("💾 Guardar Correcciones"):
                        if actualizar_metodos_pago(ws_ventas, df_edit): st.success("Listo."); st.rerun()

                # CÁLCULOS
                v_total = df_ventas["Total_Dinero"].sum()
                v_efec = df_ventas[df_ventas["Metodo_Pago_Real_Auditado"] == "Efectivo"]["Total_Dinero"].sum()
                v_digi = df_ventas[df_ventas["Metodo_Pago_Real_Auditado"].str.contains("Nequi|Davi|Banco|Transf", case=False, na=False)]["Total_Dinero"].sum()
                v_tarj = df_ventas[df_ventas["Metodo_Pago_Real_Auditado"].isin(["Tarjeta", "Datafono"])]["Total_Dinero"].sum()
                
                g_efec = df_gastos[df_gastos["Metodo_Pago"].str.contains("Efectivo", case=False)]["Monto"].sum() if not df_gastos.empty else 0
                c_efec = df_compras[df_compras["Metodo_Pago"].str.contains("Efectivo", case=False)]["Precio_Total_Pagado"].sum() if not df_compras.empty else 0

                total_salidas_efectivo = g_efec + c_efec
                saldo_teorico = v_efec - total_salidas_efectivo

                # RESUMEN
                st.markdown("#### Resumen Financiero")
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("VENTA TOTAL", formato_moneda_co(v_total))
                k2.metric("Efectivo", formato_moneda_co(v_efec))
                k3.metric("Digital", formato_moneda_co(v_digi))
                k4.metric("Tarjetas", formato_moneda_co(v_tarj))
                
                st.markdown("---")
                # PROFIT
                c_p1, c_p2 = st.columns([1, 2])
                pct_prof = c_p1.number_input("% Ahorro", value=5, min_value=1)
                monto_p = v_total * (pct_prof/100)
                c_p2.info(f"👉 Ahorrar: **{formato_moneda_co(monto_p)}**")
                check_ahorro = c_p2.checkbox("✅ Transferido")
                
                st.markdown("---")
                # ARQUEO
                st.subheader("💵 Arqueo de Efectivo")
                c1, c2, c3 = st.columns(3)
                c1.metric("(+) Entradas Efec.", formato_moneda_co(v_efec))
                c2.metric("(-) Salidas Efec.", formato_moneda_co(total_salidas_efectivo))
                c3.metric("(=) TEÓRICO", formato_moneda_co(saldo_teorico))
                
                col_r, col_d = st.columns(2)
                real = col_r.number_input("¿Cuánto contaste?", min_value=0.0, step=500.0)
                diff = real - saldo_teorico
                
                if diff == 0: st.success("✅ CUADRADO")
                elif diff > 0: st.info(f"🔵 SOBRA: {formato_moneda_co(diff)}")
                else: st.error(f"🔴 FALTA: {formato_moneda_co(diff)}")

                st.markdown("---")
                c_z, c_nota = st.columns([1, 2])
                num_z = c_z.text_input("🧾 N° Cierre Loyverse (Z)", placeholder="#1024")
                not_cierre = c_nota.text_area("Notas")
                
                if st.button("🔒 CERRAR CAJA", type="primary", use_container_width=True):
                    est_ahorro = "GUARDADO" if check_ahorro else "PENDIENTE"
                    
                    # DICCIONARIO DE DATOS (Mapeo Seguro)
                    datos_guardar = {
                        "Fecha": fecha_str,
                        "Hora_Cierre": datetime.now(ZONA_HORARIA).strftime("%H:%M"),
                        "Venta_Total_Bruta": v_total,          # NUEVO
                        "Venta_Efectivo": v_efec,              # NUEVO
                        "Gastos_Pagados_Efectivo": total_salidas_efectivo, # NUEVO
                        "Saldo_Teorico_Efectivo": saldo_teorico,
                        "Saldo_Real_Contado": real,
                        "Diferencia": diff,
                        "Total_Nequi": v_digi,
                        "Total_Tarjetas": v_tarj,
                        "Notas": not_cierre,
                        "Profit_Retenido": monto_p,
                        "Estado_Ahorro": est_ahorro,
                        "Numero_Cierre_Loyverse": str(num_z)
                    }
                    
                    if guardar_cierre_completo(sheet, datos_guardar):
                        st.balloons(); st.success("Guardado."); st.cache_data.clear(); time.sleep(2); st.rerun()

        st.markdown("---")
        st.caption("📜 Historial reciente")
        df_full = cargar_historial_completo(sheet)
        if not df_full.empty:
            df_ver = df_full.head(5).copy()
            # Mapeo de columnas existentes
            cols_ver = ["Fecha", "Venta_Total_Bruta", "Saldo_Real_Contado", "Diferencia", "Notas"]
            cols_exist = [c for c in cols_ver if c in df_ver.columns]
            
            # Formato
            if "Venta_Total_Bruta" in df_ver.columns: df_ver["Venta_Total_Bruta"] = pd.to_numeric(df_ver["Venta_Total_Bruta"], errors='coerce').apply(formato_moneda_co)
            if "Saldo_Real_Contado" in df_ver.columns: df_ver["Saldo_Real_Contado"] = pd.to_numeric(df_ver["Saldo_Real_Contado"], errors='coerce').apply(formato_moneda_co)
            if "Diferencia" in df_ver.columns: df_ver["Diferencia"] = pd.to_numeric(df_ver["Diferencia"], errors='coerce').apply(formato_moneda_co)

            st.dataframe(df_ver[cols_exist], use_container_width=True, hide_index=True)

    # TAB 2: AHORRO
    with tab_ahorro:
        st.subheader("🐷 Fondo de Reservas")
        df_h = cargar_historial_completo(sheet)
        if not df_h.empty and "Profit_Retenido" in df_h.columns:
            df_h["Profit_Retenido"] = pd.to_numeric(df_h["Profit_Retenido"], errors='coerce').fillna(0)
            
            total_banco = df_h[df_h["Estado_Ahorro"] == "GUARDADO"]["Profit_Retenido"].sum()
            total_deuda = df_h[df_h["Estado_Ahorro"] == "PENDIENTE"]["Profit_Retenido"].sum()
            
            k1, k2 = st.columns(2)
            k1.metric("💰 Total en Banco", formato_moneda_co(total_banco))
            k2.metric("⚠️ Pendiente", formato_moneda_co(total_deuda), delta_color="inverse")
            
            pendientes = df_h[df_h["Estado_Ahorro"] == "PENDIENTE"]
            if not pendientes.empty:
                st.markdown("### 🟠 Pagar Pendientes")
                opciones = pendientes.apply(lambda x: f"{x['Fecha']} - {formato_moneda_co(x['Profit_Retenido'])}", axis=1).tolist()
                pago = st.selectbox("Selecciona:", opciones)
                if st.button("✅ REGISTRAR PAGO"):
                    if pagar_ahorro_pendiente(sheet, pago.split(" - ")[0]):
                        st.success("Pagado."); st.cache_data.clear(); time.sleep(1); st.rerun()
            else: st.success("¡Al día!")
            
            st.dataframe(df_h[["Fecha", "Profit_Retenido", "Estado_Ahorro"]].sort_values("Fecha", ascending=False), use_container_width=True)
        else: st.info("Sin datos.")
