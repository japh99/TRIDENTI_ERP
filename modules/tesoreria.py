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

def formato_moneda_co(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try:
        return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

# --- FUNCIONES DE CARGA Y ESTADO ---

def verificar_estructura_cierres(ws):
    """Asegura que exista la columna de Numero_Cierre_Loyverse"""
    try:
        headers = ws.row_values(1)
        if "Numero_Cierre_Loyverse" not in headers:
            # Si falta, la agregamos al final (Columna 11)
            ws.update_cell(1, 11, "Numero_Cierre_Loyverse")
    except: pass

def verificar_cierre_existente(sheet, fecha_str):
    try:
        ws = sheet.worksheet(HOJA_CIERRES)
        verificar_estructura_cierres(ws)
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
        df = leer_datos_seguro(ws)
        # Asegurar que existan columnas clave
        if "Numero_Cierre_Loyverse" not in df.columns: df["Numero_Cierre_Loyverse"] = ""
        return df
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
        # 1. VENTAS (CON LIMPIEZA DE DUPLICADOS)
        ws_ventas = sheet.worksheet(HOJA_VENTAS)
        data_ventas = ws_ventas.get_all_records()
        df_ventas = pd.DataFrame(data_ventas)
        
        if not df_ventas.empty:
            df_ventas["Fecha"] = df_ventas["Fecha"].astype(str)
            # Filtro de fecha
            df_ventas = df_ventas[df_ventas["Fecha"] == fecha_str]
            
            # --- CORRECCIÓN MATEMÁTICA: Eliminar duplicados exactos ---
            # A veces el robot descarga dos veces lo mismo. Limpiamos.
            # Usamos ID_Plato + Hora + Recibo como llave única
            df_ventas = df_ventas.drop_duplicates(subset=["Numero_Recibo", "ID_Plato", "Hora"])
            
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

def guardar_cierre(sheet, datos):
    try:
        try:
            ws = sheet.worksheet(HOJA_CIERRES)
        except:
            ws = sheet.add_worksheet(title=HOJA_CIERRES, rows="1000", cols="11")
            ws.append_row(["Fecha", "Hora_Cierre", "Saldo_Teorico_Efectivo", "Saldo_Real_Contado", "Diferencia", "Total_Nequi", "Total_Tarjetas", "Notas", "Profit_Retenido", "Estado_Ahorro", "Numero_Cierre_Loyverse"])
        
        ws.append_rows([datos])
        return True
    except Exception as e:
        st.error(f"Error guardando: {e}")
        return False

def pagar_ahorro_pendiente(sheet, fecha_pago):
    try:
        ws = sheet.worksheet(HOJA_CIERRES)
        fechas = ws.col_values(1)
        try:
            fila_index = fechas.index(str(fecha_pago)) + 1 
        except ValueError:
            return False 
        
        # Buscar columna Estado_Ahorro (header)
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

    tab_caja, tab_ahorro = st.tabs(["📝 GESTIÓN DE CAJA (DIARIO)", "🐷 BANCO DE AHORRO (PROFIT FIRST)"])

    # ==========================
    # TAB 1: GESTIÓN DE CAJA
    # ==========================
    with tab_caja:
        hoy = datetime.now(ZONA_HORARIA).date()
        col_f, col_s = st.columns([1, 2])
        fecha_cierre = col_f.date_input("Fecha de Arqueo", value=hoy)
        fecha_str = fecha_cierre.strftime("%Y-%m-%d")

        datos_cierre = verificar_cierre_existente(sheet, fecha_str)

        # --- YA CERRADO ---
        if datos_cierre is not None:
            num_z = datos_cierre.get("Numero_Cierre_Loyverse", "S/N")
            with col_s: 
                st.success(f"✅ **DÍA CERRADO** (Z-Report: #{num_z})")
            
            # Recuperar datos
            teorico = float(limpiar_numero(datos_cierre.get("Saldo_Teorico_Efectivo", 0)))
            real = float(limpiar_numero(datos_cierre.get("Saldo_Real_Contado", 0)))
            diff = float(limpiar_numero(datos_cierre.get("Diferencia", 0)))
            profit = float(limpiar_numero(datos_cierre.get("Profit_Retenido", 0)))
            estado_ah = datos_cierre.get("Estado_Ahorro", "-")
            notas = datos_cierre.get("Notas", "")
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Debía Haber", formato_moneda_co(teorico))
            c2.metric("Se Contó", formato_moneda_co(real))
            c3.metric("Diferencia", formato_moneda_co(diff), delta_color="off")
            
            st.info(f"🐷 **Ahorro del día:** {formato_moneda_co(profit)} ({estado_ah})")
            st.text_area("Notas Guardadas:", value=notas, disabled=True)
            
            if st.button("🗑️ REABRIR CAJA (Borrar y Corregir)", type="secondary"):
                if reabrir_caja(sheet, fecha_str): 
                    st.warning("Reabriendo..."); st.cache_data.clear(); time.sleep(1); st.rerun()

        # --- ABIERTO ---
        else:
            with col_s: st.warning("⚠️ **PENDIENTE**")
            
            # Carga con limpieza de duplicados
            df_ventas, df_gastos, df_compras, ws_ventas = cargar_movimientos(sheet, fecha_str)

            if df_ventas is None or df_ventas.empty:
                st.error("No hay ventas registradas. Ve a 'Ventas' y descarga el día primero.")
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
                
                # Digitales
                mask_digi = df_ventas["Metodo_Pago_Real_Auditado"].str.contains("Nequi|Davi|Banco|Transf", case=False, na=False)
                v_digi = df_ventas[mask_digi]["Total_Dinero"].sum()
                
                v_tarj = df_ventas[df_ventas["Metodo_Pago_Real_Auditado"].isin(["Tarjeta", "Datafono"])]["Total_Dinero"].sum()
                
                # Egresos
                g_efec = df_gastos[df_gastos["Metodo_Pago"].str.contains("Efectivo", case=False)]["Monto"].sum() if not df_gastos.empty else 0
                c_efec = df_compras[df_compras["Metodo_Pago"].str.contains("Efectivo", case=False)]["Precio_Total_Pagado"].sum() if not df_compras.empty else 0

                saldo_teorico = v_efec - g_efec - c_efec

                # RESUMEN DEL DÍA
                st.markdown("#### Resumen Financiero")
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("VENTA TOTAL", formato_moneda_co(v_total))
                k2.metric("Efectivo", formato_moneda_co(v_efec))
                k3.metric("Digital", formato_moneda_co(v_digi))
                k4.metric("Tarjetas", formato_moneda_co(v_tarj))
                
                st.markdown("---")
                
                # PROFIT FIRST
                c_p1, c_p2 = st.columns([1, 2])
                pct_prof = c_p1.number_input("% Ahorro", value=5, min_value=1)
                monto_p = v_total * (pct_prof/100)
                c_p2.info(f"👉 **Ahorrar hoy:** {formato_moneda_co(monto_p)}")
                check_ahorro = c_p2.checkbox("✅ Confirmo transferencia")
                
                st.markdown("---")
                
                # ARQUEO
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
                    elif diff > 0: st.info(f"🔵 SOBRA: {formato_moneda_co(diff)}")
                    else: st.error(f"🔴 FALTA: {formato_moneda_co(diff)}")

                # CIERRE FINAL
                st.markdown("---")
                c_z, c_nota = st.columns([1, 2])
                num_z = c_z.text_input("🧾 N° Cierre Loyverse (Z)", placeholder="#1023")
                not_cierre = c_nota.text_area("Notas", placeholder="Diferencias, novedades...")
                
                if st.button("🔒 CERRAR CAJA", type="primary", use_container_width=True):
                    est_ahorro = "GUARDADO" if check_ahorro else "PENDIENTE"
                    datos = [
                        fecha_str, datetime.now(ZONA_HORARIA).strftime("%H:%M"),
                        float(saldo_teorico), float(real), float(diff), 
                        float(v_digi), float(v_tarj), 
                        not_cierre, float(monto_p), est_ahorro, 
                        str(num_z)
                    ]
                    if guardar_cierre(sheet, datos):
                        st.balloons(); st.success("Guardado."); st.cache_data.clear(); time.sleep(2); st.rerun()
        
        # HISTORIAL CORTO
        st.markdown("---")
        df_full = cargar_historial_completo(sheet)
        if not df_full.empty:
            st.caption("📜 Últimos cierres:")
            df_ver = df_full.head(5).copy()
            # Formato visual seguro
            if "Numero_Cierre_Loyverse" not in df_ver.columns: df_ver["Numero_Cierre_Loyverse"] = "S/N"
            
            st.dataframe(df_ver[["Fecha", "Numero_Cierre_Loyverse", "Saldo_Real_Contado", "Diferencia", "Notas"]], use_container_width=True, hide_index=True)

    # ==========================
    # TAB 2: BANCO DE AHORRO
    # ==========================
    with tab_ahorro:
        st.subheader("🐷 Fondo de Reservas")
        
        df_h = cargar_historial_completo(sheet)
        if not df_h.empty and "Profit_Retenido" in df_h.columns:
            df_h["Profit_Retenido"] = pd.to_numeric(df_h["Profit_Retenido"], errors='coerce').fillna(0)
            
            guardados = df_h[df_h["Estado_Ahorro"] == "GUARDADO"]
            pendientes = df_h[df_h["Estado_Ahorro"] == "PENDIENTE"]
            
            total_banco = guardados["Profit_Retenido"].sum()
            total_deuda = pendientes["Profit_Retenido"].sum()
            
            # --- TARJETAS CLARAS ---
            k1, k2 = st.columns(2)
            k1.metric("💰 Alcancía Total (Acumulado)", formato_moneda_co(total_banco))
            k2.metric("⚠️ Deuda al Ahorro (Pendiente)", formato_moneda_co(total_deuda), delta_color="inverse")
            
            # --- SECCIÓN DE PAGO DE DEUDA ---
            if not pendientes.empty:
                st.markdown("### 🟠 Pagar Ahorros Pendientes")
                st.caption("Selecciona un día para marcarlo como transferido.")
                
                lista_pagar = pendientes.apply(lambda x: f"{x['Fecha']} - {formato_moneda_co(x['Profit_Retenido'])}", axis=1).tolist()
                pago_sel = st.selectbox("Transferir Ahorro de:", lista_pagar)
                
                if st.button("✅ YA HICE LA TRANSFERENCIA"):
                    fecha_pago = pago_sel.split(" - ")[0]
                    if pagar_ahorro_pendiente(sheet, fecha_pago):
                        st.cache_data.clear() # Limpiar memoria para ver el cambio
                        st.success("¡Registrado! El dinero ha pasado al banco."); time.sleep(2); st.rerun()
                    else: st.error("Error actualizando.")
            else:
                st.success("🎉 ¡Estás al día con tus ahorros!")
            
            # --- HISTORIAL COMPLETO ---
            st.markdown("---")
            st.write("#### 📜 Movimientos de la Alcancía")
            df_ver = df_h[["Fecha", "Profit_Retenido", "Estado_Ahorro"]].copy()
            df_ver["Profit_Retenido"] = df_ver["Profit_Retenido"].apply(formato_moneda_co)
            st.dataframe(df_ver, use_container_width=True, hide_index=True)
        else:
            st.info("Sin datos de ahorro.")
