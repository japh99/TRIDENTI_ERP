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

# --- FUNCIONES DE ESTADO (CERRADO/ABIERTO) ---

def verificar_cierre_existente(sheet, fecha_str):
    """Revisa si el día ya fue cerrado."""
    try:
        ws = sheet.worksheet(HOJA_CIERRES)
        df = leer_datos_seguro(ws)
        if not df.empty and "Fecha" in df.columns:
            # Convertir a string para comparar
            df["Fecha"] = df["Fecha"].astype(str)
            cierre = df[df["Fecha"] == fecha_str]
            if not cierre.empty:
                return cierre.iloc[0] # Retorna los datos del cierre
        return None
    except: return None

def reabrir_caja(sheet, fecha_str):
    """Borra el cierre para permitir editar."""
    try:
        ws = sheet.worksheet(HOJA_CIERRES)
        data = ws.get_all_records()
        if not data: return True
        
        df = pd.DataFrame(data)
        df["Fecha"] = df["Fecha"].astype(str)
        
        # Filtro Inverso: Dejamos todo lo que NO sea hoy
        df_limpio = df[df["Fecha"] != fecha_str]
        
        ws.clear()
        # Reponer encabezados y datos
        ws.update([df_limpio.columns.values.tolist()] + df_limpio.values.tolist())
        return True
    except Exception as e:
        st.error(f"Error al reabrir: {e}")
        return False

# --- FUNCIONES DE CARGA ---
def cargar_movimientos(sheet, fecha_str):
    try:
        # Ventas
        ws_ventas = sheet.worksheet(HOJA_VENTAS)
        data_ventas = ws_ventas.get_all_records()
        df_ventas = pd.DataFrame(data_ventas)
        if not df_ventas.empty:
            df_ventas["Fecha"] = df_ventas["Fecha"].astype(str)
            df_ventas = df_ventas[df_ventas["Fecha"] == fecha_str]
            df_ventas["Total_Dinero"] = pd.to_numeric(df_ventas["Total_Dinero"], errors='coerce').fillna(0)
        
        # Gastos
        try:
            ws_gastos = sheet.worksheet(HOJA_GASTOS)
            df_gastos = leer_datos_seguro(ws_gastos)
            if not df_gastos.empty:
                df_gastos["Fecha"] = df_gastos["Fecha"].astype(str)
                df_gastos = df_gastos[df_gastos["Fecha"] == fecha_str]
                df_gastos["Monto"] = pd.to_numeric(df_gastos["Monto"], errors='coerce').fillna(0)
        except: df_gastos = pd.DataFrame()

        # Compras
        try:
            ws_compras = sheet.worksheet(HOJA_COMPRAS)
            df_compras = leer_datos_seguro(ws_compras)
            if not df_compras.empty:
                df_compras["Fecha_Registro"] = df_compras["Fecha_Registro"].astype(str)
                df_compras = df_compras[df_compras["Fecha_Registro"] == fecha_str]
                df_compras["Precio_Total_Pagado"] = pd.to_numeric(df_compras["Precio_Total_Pagado"], errors='coerce').fillna(0)
        except: df_compras = pd.DataFrame()

        return df_ventas, df_gastos, df_compras, ws_ventas

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
            ws.append_row(["Fecha", "Hora_Cierre", "Saldo_Teorico_Efectivo", "Saldo_Real_Contado", "Diferencia", "Total_Nequi", "Total_Tarjetas", "Notas", "Profit_Retenido", "Estado_Ahorro"])
        
        ws.append_rows([datos])
        return True
    except: return False

# --- INTERFAZ ---
def show(sheet):
    st.title("🔐 Tesorería Central")
    st.markdown("---")
    
    if not sheet: return

    hoy = datetime.now(ZONA_HORARIA).date()
    col_fecha, col_estado = st.columns([1, 2])
    
    with col_fecha:
        fecha_cierre = st.date_input("Fecha de Arqueo", value=hoy)
        fecha_str = fecha_cierre.strftime("%Y-%m-%d")

    # 1. VERIFICAR SI ESTÁ CERRADO
    datos_cierre_existente = verificar_cierre_existente(sheet, fecha_str)

    # --- ESCENARIO A: YA CERRADO (SOLO LECTURA) ---
    if datos_cierre_existente is not None:
        with col_estado:
            st.success(f"✅ **DÍA CERRADO** (Hora: {datos_cierre_existente.get('Hora_Cierre', 'N/A')})")
        
        st.info("Resumen del Cierre:")
        
        # Recuperar valores
        teorico = float(limpiar_numero(datos_cierre_existente.get("Saldo_Teorico_Efectivo", 0)))
        real = float(limpiar_numero(datos_cierre_existente.get("Saldo_Real_Contado", 0)))
        diferencia = float(limpiar_numero(datos_cierre_existente.get("Diferencia", 0)))
        notas = datos_cierre_existente.get("Notas", "")
        profit = float(limpiar_numero(datos_cierre_existente.get("Profit_Retenido", 0)))
        estado_ahorro = datos_cierre_existente.get("Estado_Ahorro", "-")

        c1, c2, c3 = st.columns(3)
        c1.metric("Debía Haber", formato_moneda_co(teorico))
        c2.metric("Se Contó", formato_moneda_co(real))
        c3.metric("Diferencia", formato_moneda_co(diferencia), delta_color="off")
        
        st.write(f"🐷 **Ahorro Profit First:** {formato_moneda_co(profit)} ({estado_ahorro})")
        st.text_area("Notas:", value=notas, disabled=True)
        
        st.markdown("---")
        
        # BOTÓN DE REAPERTURA
        col_warn, col_btn = st.columns([2, 1])
        col_warn.warning("¿Necesitas corregir algo? Reabre la caja.")
        if col_btn.button("🗑️ REABRIR CAJA", type="primary", use_container_width=True):
            with st.spinner("Eliminando cierre..."):
                if reabrir_caja(sheet, fecha_str):
                    st.success("Caja abierta. Recargando...")
                    st.cache_data.clear()
                    time.sleep(1)
                    st.rerun()
        return

    # --- ESCENARIO B: CAJA ABIERTA (FORMULARIO ACTIVO) ---
    with col_estado:
        st.warning("⚠️ **CAJA ABIERTA** (Pendiente)")

    df_ventas, df_gastos, df_compras, ws_ventas = cargar_movimientos(sheet, fecha_str)

    if df_ventas is None or df_ventas.empty:
        st.error("No hay ventas registradas. Descarga el día primero.")
        return

    # AUDITORÍA
    with st.expander("🛠️ Paso 1: Auditoría (Corregir Medios de Pago)", expanded=False):
        df_audit = df_ventas[["Hora", "Numero_Recibo", "Total_Dinero", "Metodo_Pago_Loyverse", "Metodo_Pago_Real_Auditado"]].drop_duplicates(subset=["Numero_Recibo"])
        df_editado = st.data_editor(
            df_audit,
            column_config={"Metodo_Pago_Real_Auditado": st.column_config.SelectboxColumn("MÉTODO REAL", options=["Efectivo", "Nequi", "Tarjeta", "Rappi", "Otro"], required=True)},
            hide_index=True, use_container_width=True
        )
        if st.button("💾 GUARDAR CORRECCIONES"):
            if actualizar_metodos_pago(ws_ventas, df_editado):
                st.success("✅ Corregido."); time.sleep(1); st.rerun()

    # CÁLCULOS
    v_total = df_ventas["Total_Dinero"].sum()
    v_efec = df_ventas[df_ventas["Metodo_Pago_Real_Auditado"] == "Efectivo"]["Total_Dinero"].sum()
    
    # Suma Digital
    mask_digi = df_ventas["Metodo_Pago_Real_Auditado"].str.contains("Nequi|Davi|Banco|Transf", case=False, na=False)
    v_digi = df_ventas[mask_digi]["Total_Dinero"].sum()
    
    # Suma Tarjetas
    mask_tarj = df_ventas["Metodo_Pago_Real_Auditado"].str.contains("Tarjeta|Datafono", case=False, na=False)
    v_tarj = df_ventas[mask_tarj]["Total_Dinero"].sum()
    
    # Egresos Efectivo
    g_efec = df_gastos[df_gastos["Metodo_Pago"].str.contains("Efectivo", case=False)]["Monto"].sum() if not df_gastos.empty else 0
    c_efec = df_compras[df_compras["Metodo_Pago"].str.contains("Efectivo", case=False)]["Precio_Total_Pagado"].sum() if not df_compras.empty and "Metodo_Pago" in df_compras.columns else 0

    saldo_teorico = v_efec - g_efec - c_efec

    # RESUMEN
    st.header(f"Resumen del Día")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("💰 VENTA TOTAL", formato_moneda_co(v_total))
    k2.metric("💵 Efectivo", formato_moneda_co(v_efec))
    k3.metric("📱 Digital", formato_moneda_co(v_digi))
    k4.metric("💳 Tarjetas", formato_moneda_co(v_tarj))

    st.markdown("---")
    
    # PROFIT FIRST
    st.subheader("💰 Fondo de Ahorro")
    c_p1, c_p2 = st.columns([1, 2])
    porc = c_p1.number_input("% Retención", value=5, min_value=1, max_value=50)
    monto_p = v_total * (porc/100)
    c_p2.info(f"👉 Transfiere: **{formato_moneda_co(monto_p)}**")
    check_ahorro = c_p2.checkbox("✅ Confirmo transferencia")

    st.markdown("---")
    
    # ARQUEO
    st.header("💵 Paso 2: Arqueo")
    c1, c2, c3 = st.columns(3)
    c1.metric("(+) Entradas", formato_moneda_co(v_efec))
    c2.metric("(-) Salidas", formato_moneda_co(g_efec + c_efec))
    c3.metric("(=) DEBE HABER", formato_moneda_co(saldo_teorico))
    
    col_r, col_d = st.columns(2)
    real = col_r.number_input("¿Cuánto contaste?", min_value=0.0, step=500.0)
    diff = real - saldo_teorico
    
    with col_d:
        if diff == 0: st.success("✅ CUADRADO")
        elif diff > 0: st.info(f"🔵 SOBRA: {formato_moneda_co(diff)}")
        else: st.error(f"🔴 FALTA: {formato_moneda_co(diff)}")

    st.markdown("---")
    notas = st.text_area("Notas del Cierre")
    
    if st.button("🔒 CERRAR CAJA DEFINITIVAMENTE", type="primary", use_container_width=True):
        datos = [
            fecha_str, datetime.now(ZONA_HORARIA).strftime("%H:%M"),
            float(saldo_teorico), float(real), float(diff),
            float(v_digi), float(v_tarj), str(notas), float(monto_p),
            "GUARDADO" if check_ahorro else "PENDIENTE"
        ]
        if guardar_cierre(sheet, datos):
            st.balloons()
            st.success("✅ Cierre Guardado.")
            st.cache_data.clear()
            time.sleep(2); st.rerun()

    # HISTORIAL
    st.markdown("---")
    try:
        ws_h = sheet.worksheet(HOJA_CIERRES)
        df_h = leer_datos_seguro(ws_h)
        if not df_h.empty:
            st.caption("📜 Últimos 5 cierres:")
            st.dataframe(df_h.sort_values("Fecha", ascending=False).head(5), use_container_width=True, hide_index=True)
    except: pass
