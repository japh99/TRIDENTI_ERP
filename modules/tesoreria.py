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

# --- FUNCIONES BASE DE DATOS ---

def asegurar_columnas(ws):
    try:
        current = ws.row_values(1)
        if not current:
            ws.append_row(HEADERS_CIERRE)
            return
        
        faltantes = [c for c in HEADERS_CIERRE if c not in current]
        if faltantes:
            next_col = len(current) + 1
            for col in faltantes:
                ws.update_cell(1, next_col, col)
                next_col += 1
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
            if isinstance(val, (int, float)): fila.append(float(val))
            else: fila.append(str(val))
            
        ws.append_row(fila)
        return True
    except Exception as e:
        st.error(f"Error guardando: {e}")
        return False

# ... (Resto de funciones de carga igual que antes) ...
# Para ahorrar espacio, incluiré las funciones clave modificadas:

def cargar_datos_ahorro(sheet):
    """Carga segura de historial de ahorros."""
    try:
        ws_c = obtener_o_crear_hoja(sheet, HOJA_CIERRES, HEADERS_CIERRE)
        df_c = leer_datos_seguro(ws_c)
        if not df_c.empty:
            df_c["Profit_Retenido"] = pd.to_numeric(df_c["Profit_Retenido"], errors='coerce').fillna(0)
        
        ws_r = obtener_o_crear_hoja(sheet, HOJA_RETIROS, HEADERS_RETIROS)
        df_r = leer_datos_seguro(ws_r)
        if not df_r.empty:
            df_r["Monto_Retirado"] = pd.to_numeric(df_r["Monto_Retirado"], errors='coerce').fillna(0)
            
        return df_c, df_r
    except: return pd.DataFrame(), pd.DataFrame()

# --- REUTILIZAR FUNCIONES DE CARGA ANTERIORES ---
# (Asegúrate de copiar estas funciones del código anterior si no las tienes a mano, 
# pero aquí está la estructura completa para evitar errores)

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

def cargar_movimientos(sheet, fecha_str):
    try:
        # Ventas
        ws_v = sheet.worksheet(HOJA_VENTAS)
        df_v = pd.DataFrame(ws_v.get_all_records())
        if not df_v.empty:
            df_v["Fecha"] = df_v["Fecha"].astype(str)
            df_v = df_v[df_v["Fecha"] == fecha_str]
            df_v = df_v.drop_duplicates(subset=["Numero_Recibo", "ID_Plato", "Hora"])
            df_v["Total_Dinero"] = pd.to_numeric(df_v["Total_Dinero"], errors='coerce').fillna(0)
        
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

        return df_v, df_g, df_c, ws_v
    except: return None, None, None, None

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
        try: idx = fechas.index(str(fecha_pago)) + 1 
        except: return False
        
        headers = ws.row_values(1)
        try: c_idx = headers.index("Estado_Ahorro") + 1
        except: c_idx = 10
        
        ws.update_cell(idx, c_idx, "GUARDADO")
        return True
    except: return False

# --- INTERFAZ ---

def show(sheet):
    st.title("🔐 Tesorería Central")
    st.markdown("---")
    
    if not sheet: return

    tab1, tab2 = st.tabs(["📝 GESTIÓN DE CAJA", "🐷 BANCO DE AHORRO"])

    # TAB 1
    with tab1:
        hoy = datetime.now(ZONA_HORARIA).date()
        c_f, c_s = st.columns([1, 2])
        fecha_cierre = c_f.date_input("Fecha", value=hoy)
        fecha_str = fecha_cierre.strftime("%Y-%m-%d")

        datos_cierre = verificar_cierre_existente(sheet, fecha_str)

        if datos_cierre is not None:
            # CERRADO
            with c_s: st.success(f"✅ DÍA CERRADO (Z: {datos_cierre.get('Numero_Cierre_Loyverse', '-')})")
            
            # Recuperar
            teorico = float(limpiar_numero(datos_cierre.get("Saldo_Teorico_Efectivo", 0)))
            real = float(limpiar_numero(datos_cierre.get("Saldo_Real_Contado", 0)))
            diff = float(limpiar_numero(datos_cierre.get("Diferencia", 0)))
            profit = float(limpiar_numero(datos_cierre.get("Profit_Retenido", 0)))
            estado_ah = datos_cierre.get("Estado_Ahorro", "-")
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Debía Haber", formato_moneda_co(teorico))
            c2.metric("Se Contó", formato_moneda_co(real))
            c3.metric("Diferencia", formato_moneda_co(diff), delta_color="off")
            
            st.info(f"🐷 Ahorro: **{formato_moneda_co(profit)}** ({estado_ah})")
            
            if st.button("🗑️ REABRIR CAJA", type="secondary"):
                if reabrir_caja(sheet, fecha_str): st.success("Reabierto."); time.sleep(1); st.rerun()

        else:
            # ABIERTO
            with c_s: st.warning("⚠️ PENDIENTE")
            df_v, df_g, df_c, ws_v = cargar_movimientos(sheet, fecha_str)

            v_tot=0; v_ef=0; v_dig=0; v_tar=0; g_ef=0; c_ef=0
            
            if df_v is not None and not df_v.empty:
                v_tot = df_v["Total_Dinero"].sum()
                v_ef = df_v[df_v["Metodo_Pago_Real_Auditado"]=="Efectivo"]["Total_Dinero"].sum()
                v_dig = df_v[df_v["Metodo_Pago_Real_Auditado"].str.contains("Nequi|Davi", case=False)]["Total_Dinero"].sum()
                v_tar = df_v[df_v["Metodo_Pago_Real_Auditado"].isin(["Tarjeta", "Datafono"])]["Total_Dinero"].sum()
                
                g_ef = df_g[df_g["Metodo_Pago"].str.contains("Efectivo", case=False)]["Monto"].sum() if not df_g.empty else 0
                c_ef = df_c[df_c["Metodo_Pago"].str.contains("Efectivo", case=False)]["Precio_Total_Pagado"].sum() if not df_c.empty else 0

            saldo_teo = v_ef - g_ef - c_ef

            st.markdown("#### Resumen Financiero")
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("VENTA TOTAL", formato_moneda_co(v_tot))
            k2.metric("Efectivo", formato_moneda_co(v_ef))
            k3.metric("Digital", formato_moneda_co(v_dig))
            k4.metric("Tarjetas", formato_moneda_co(v_tar))

            st.markdown("---")
            
            # --- PROFIT FIRST MEJORADO ---
            st.subheader("💰 Fondo de Ahorro")
            cp1, cp2 = st.columns([1, 2])
            pct = cp1.number_input("% Ahorro", value=5, min_value=0)
            monto_p = v_tot * (pct/100)
            
            with cp2:
                st.info(f"👉 Transferir: **{formato_moneda_co(monto_p)}**")
                # Selector explícito para evitar error de checkbox
                estado_ahorro_sel = st.radio("Estado de la transferencia:", 
                                             ["🔴 Pendiente (Debo transferir luego)", "🟢 GUARDADO (Ya transferí)"],
                                             horizontal=True)

            st.markdown("---")
            # ARQUEO
            st.subheader("💵 Arqueo")
            c1, c2, c3 = st.columns(3)
            c1.metric("(+) Entradas", formato_moneda_co(v_ef))
            c2.metric("(-) Salidas", formato_moneda_co(g_ef + c_ef))
            c3.metric("(=) TEÓRICO", formato_moneda_co(saldo_teo))
            
            cr, cd = st.columns(2)
            real = cr.number_input("¿Cuánto contaste?", min_value=0.0, step=500.0)
            diff = real - saldo_teo
            
            with cd:
                if diff == 0: st.success("✅ CUADRADO")
                else: st.error(f"Diferencia: {formato_moneda_co(diff)}")

            cz, cn = st.columns([1, 2])
            num_z = cz.text_input("N° Cierre (Z)", placeholder="#1025")
            notas = cn.text_area("Notas")
            
            if st.button("🔒 CERRAR CAJA", type="primary", use_container_width=True):
                est_final = "GUARDADO" if "🟢" in estado_ahorro_sel else "PENDIENTE"
                
                datos = {
                    "Fecha": fecha_str,
                    "Hora_Cierre": datetime.now(ZONA_HORARIA).strftime("%H:%M"),
                    "Venta_Total_Bruta": v_tot,
                    "Venta_Efectivo": v_ef,
                    "Gastos_Pagados_Efectivo": g_ef + c_ef,
                    "Saldo_Teorico_Efectivo": saldo_teo,
                    "Saldo_Real_Contado": real,
                    "Diferencia": diff,
                    "Total_Nequi": v_dig,
                    "Total_Tarjetas": v_tar,
                    "Notas": notas,
                    "Profit_Retenido": monto_p,
                    "Estado_Ahorro": est_final,
                    "Numero_Cierre_Loyverse": str(num_z)
                }
                
                if guardar_cierre(sheet, datos):
                    st.balloons(); st.success("Guardado."); st.cache_data.clear(); time.sleep(2); st.rerun()

    # TAB 2: BANCO
    with tab_ahorro:
        st.subheader("🐷 Banco de Ahorro")
        df_c, df_r = cargar_datos_ahorro(sheet)
        
        if not df_c.empty:
            guardados = df_c[df_c["Estado_Ahorro"] == "GUARDADO"]["Profit_Retenido"].sum()
            retirados = df_r["Monto_Retirado"].sum() if not df_r.empty else 0
            
            # Cálculo Real: Lo que entró al banco menos lo que salió
            saldo_banco = guardados - retirados
            
            pendientes = df_c[df_c["Estado_Ahorro"] == "PENDIENTE"]["Profit_Retenido"].sum()
            
            k1, k2, k3 = st.columns(3)
            k1.metric("💰 Saldo Disponible", formato_moneda_co(saldo_banco))
            k2.metric("📥 Total Histórico", formato_moneda_co(guardados))
            k3.metric("⚠️ Pendiente", formato_moneda_co(pendientes), delta_color="inverse")
            
            st.markdown("---")
            
            # PAGAR PENDIENTES
            df_pend = df_c[df_c["Estado_Ahorro"] == "PENDIENTE"]
            if not df_pend.empty:
                st.write("### 🟠 Pagar Deuda de Ahorro")
                lista = df_pend.apply(lambda x: f"{x['Fecha']} - {formato_moneda_co(x['Profit_Retenido'])}", axis=1).tolist()
                sel = st.selectbox("Pagar:", lista)
                if st.button("✅ REGISTRAR PAGO"):
                    if pagar_ahorro_pendiente(sheet, sel.split(" - ")[0]):
                        st.success("Listo."); st.cache_data.clear(); time.sleep(1); st.rerun()
            
            # RETIROS
            st.write("### 💸 Retirar")
            c_ret1, c_ret2 = st.columns(2)
            m_ret = c_ret1.number_input("Monto", min_value=0.0, step=50000.0)
            mot = c_ret2.text_input("Motivo")
            resp = st.text_input("Responsable")
            
            if st.button("🚨 RETIRAR", type="primary"):
                if m_ret <= saldo_banco and m_ret > 0:
                    if registrar_retiro_profit(sheet, m_ret, mot, resp):
                        st.success("Retiro OK."); st.cache_data.clear(); time.sleep(1); st.rerun()
                else: st.error("Fondos insuficientes.")
            
            # HISTORIAL LIMPIO
            st.markdown("---")
            st.write("#### 📜 Movimientos Recientes")
            if not df_c.empty:
                # Filtrar solo los > 0 para no ensuciar
                df_show = df_c[df_c["Profit_Retenido"] > 0].copy()
                df_show["Profit_Retenido"] = df_show["Profit_Retenido"].apply(formato_moneda_co)
                st.dataframe(df_show[["Fecha", "Profit_Retenido", "Estado_Ahorro"]].sort_values("Fecha", ascending=False), use_container_width=True)
        else: st.info("Sin datos.")
