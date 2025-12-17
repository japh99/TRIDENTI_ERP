import streamlit as st
import pandas as pd
from datetime import datetime, date
import time
from utils import conectar_google_sheets, ZONA_HORARIA

# --- CONFIGURACIÓN ---
HOJA_VENTAS = "LOG_VENTAS_LOYVERSE"
HOJA_GASTOS = "LOG_GASTOS"
HOJA_COMPRAS = "LOG_COMPRAS"
HOJA_CIERRES = "LOG_CIERRES_CAJA"

def formato_moneda_co(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try:
        return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return str(valor)

def cargar_movimientos(sheet, fecha_str):
    """Carga y filtra los movimientos del día seleccionado."""
    try:
        # 1. VENTAS
        ws_ventas = sheet.worksheet(HOJA_VENTAS)
        data_ventas = ws_ventas.get_all_records()
        df_ventas = pd.DataFrame(data_ventas)
        if not df_ventas.empty:
            df_ventas["Fecha"] = df_ventas["Fecha"].astype(str)
            df_ventas = df_ventas[df_ventas["Fecha"] == fecha_str]
            df_ventas["Total_Dinero"] = pd.to_numeric(df_ventas["Total_Dinero"], errors='coerce').fillna(0)
        
        # 2. GASTOS
        try:
            ws_gastos = sheet.worksheet(HOJA_GASTOS)
            data_gastos = ws_gastos.get_all_records()
            df_gastos = pd.DataFrame(data_gastos)
            if not df_gastos.empty:
                df_gastos["Fecha"] = df_gastos["Fecha"].astype(str)
                df_gastos = df_gastos[df_gastos["Fecha"] == fecha_str]
                df_gastos["Monto"] = pd.to_numeric(df_gastos["Monto"], errors='coerce').fillna(0)
        except: df_gastos = pd.DataFrame()

        # 3. COMPRAS
        try:
            ws_compras = sheet.worksheet(HOJA_COMPRAS)
            data_compras = ws_compras.get_all_records()
            df_compras = pd.DataFrame(data_compras)
            if not df_compras.empty:
                df_compras["Fecha_Registro"] = df_compras["Fecha_Registro"].astype(str)
                df_compras = df_compras[df_compras["Fecha_Registro"] == fecha_str]
                df_compras["Precio_Total_Pagado"] = pd.to_numeric(df_compras["Precio_Total_Pagado"], errors='coerce').fillna(0)
        except: df_compras = pd.DataFrame()

        return df_ventas, df_gastos, df_compras, ws_ventas

    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return None, None, None, None

def actualizar_metodos_pago(ws_ventas, df_editado):
    """Guarda las correcciones de auditoría."""
    try:
        col_recibos = ws_ventas.col_values(3) # Columna C es Numero_Recibo
        
        for index, row in df_editado.iterrows():
            recibo = str(row["Numero_Recibo"])
            nuevo_metodo = row["Metodo_Pago_Real_Auditado"]
            metodo_original = row["Metodo_Pago_Loyverse"]
            
            if nuevo_metodo != metodo_original:
                try:
                    # Buscamos la fila exacta del recibo
                    fila = col_recibos.index(recibo) + 1 
                    # Actualizamos columna I (9) que es el Auditado
                    ws_ventas.update_cell(fila, 9, nuevo_metodo)
                except: pass
        return True
    except Exception as e:
        st.error(f"Error actualizando: {e}")
        return False

def guardar_cierre(sheet, datos):
    try:
        try:
            ws = sheet.worksheet(HOJA_CIERRES)
        except:
            ws = sheet.add_worksheet(title=HOJA_CIERRES, rows="1000", cols="11")
            ws.append_row(["Fecha", "Hora_Cierre", "Saldo_Teorico_Efectivo", "Saldo_Real_Contado", "Diferencia", "Total_Nequi", "Total_Tarjetas", "Notas", "Profit_Retenido", "Estado_Ahorro"])
        
        ws.append_rows([datos])
        return True
    except Exception as e:
        st.error(f"Error guardando cierre: {e}")
        return False

def show(sheet):
    st.title("🔐 Tesorería & Cierre")
    st.markdown("---")
    
    if not sheet: return

    hoy = datetime.now(ZONA_HORARIA).date()
    col1, _ = st.columns([1, 2])
    fecha_cierre = col1.date_input("Fecha de Arqueo", value=hoy)
    fecha_str = fecha_cierre.strftime("%Y-%m-%d")

    # CARGA DE DATOS
    df_ventas, df_gastos, df_compras, ws_ventas = cargar_movimientos(sheet, fecha_str)

    if df_ventas is None or df_ventas.empty:
        st.warning("⚠️ No hay ventas registradas para esta fecha. Ve al módulo 'Ventas' y descarga primero.")
        return

    # --- PASO 1: AUDITORÍA DE MEDIOS DE PAGO ---
    with st.expander("🛠️ Auditoría: Corregir Medios de Pago (Error Cajero)", expanded=False):
        st.info("Si el cajero marcó 'Efectivo' pero era 'Nequi', cámbialo aquí en la columna 'MÉTODO REAL'.")
        
        # Filtramos solo lo necesario para no saturar
        cols_mostrar = ["Hora", "Numero_Recibo", "Total_Dinero", "Metodo_Pago_Loyverse", "Metodo_Pago_Real_Auditado"]
        # Eliminamos duplicados de recibos (porque ventas baja plato por plato)
        df_audit = df_ventas[cols_mostrar].drop_duplicates(subset=["Numero_Recibo"])
        
        df_editado = st.data_editor(
            df_audit,
            column_config={
                "Hora": st.column_config.TextColumn(disabled=True),
                "Numero_Recibo": st.column_config.TextColumn(disabled=True),
                "Total_Dinero": st.column_config.NumberColumn(format="$%d", disabled=True),
                "Metodo_Pago_Loyverse": st.column_config.TextColumn("Original (Loyverse)", disabled=True),
                "Metodo_Pago_Real_Auditado": st.column_config.SelectboxColumn(
                    "MÉTODO REAL (Editar)",
                    options=["Efectivo", "Nequi", "Bancolombia", "Daviplata", "Transferencia", "Tarjeta", "Datafono", "Rappi", "Otro"],
                    required=True
                )
            },
            hide_index=True,
            use_container_width=True,
            key="editor_ventas"
        )
        
        # Botón para guardar correcciones
        # Comparamos si hubo cambios
        cambios = False
        if not df_editado["Metodo_Pago_Real_Auditado"].equals(df_audit["Metodo_Pago_Real_Auditado"]):
            cambios = True
            
        if cambios:
             if st.button("💾 GUARDAR CORRECCIONES DE PAGO"):
                with st.spinner("Actualizando base de datos..."):
                    if actualizar_metodos_pago(ws_ventas, df_editado):
                        st.success("✅ Correcciones aplicadas. Recalculando saldos...")
                        time.sleep(1)
                        st.rerun()

    # --- CÁLCULOS FINANCIEROS (Usando la columna Auditada) ---
    total_venta_dia = df_ventas["Total_Dinero"].sum()
    
    # 1. EFECTIVO
    ventas_efectivo = df_ventas[df_ventas["Metodo_Pago_Real_Auditado"] == "Efectivo"]["Total_Dinero"].sum()
    
    # 2. DIGITAL (Nequi, Davi, Bancolombia, Transferencia)
    # Buscamos cualquier texto que parezca digital
    mask_digital = df_ventas["Metodo_Pago_Real_Auditado"].str.contains("Nequi|Davi|Banco|Transf", case=False, na=False)
    ventas_digital = df_ventas[mask_digital]["Total_Dinero"].sum()
    
    # 3. TARJETAS (Datafono)
    mask_tarjeta = df_ventas["Metodo_Pago_Real_Auditado"].str.contains("Tarjeta|Datafono|Credito|Debito", case=False, na=False)
    ventas_tarjeta = df_ventas[mask_tarjeta]["Total_Dinero"].sum()
    
    # 4. PLATAFORMAS (Rappi, etc) - Lo que sobre
    ventas_apps = total_venta_dia - (ventas_efectivo + ventas_digital + ventas_tarjeta)

    # --- EGRESOS (Solo restan si fueron en efectivo) ---
    gastos_efectivo = 0
    if not df_gastos.empty:
        gastos_efectivo = df_gastos[df_gastos["Metodo_Pago"].str.contains("Efectivo", case=False)]["Monto"].sum()
        
    compras_efectivo = 0
    if not df_compras.empty and "Metodo_Pago" in df_compras.columns:
        compras_efectivo = df_compras[df_compras["Metodo_Pago"].str.contains("Efectivo", case=False)]["Precio_Total_Pagado"].sum()

    saldo_teorico_cajon = ventas_efectivo - gastos_efectivo - compras_efectivo

    # ==========================================
    # 📊 SECCIÓN VISUAL PRINCIPAL
    # ==========================================
    
    st.header(f"📊 Resumen Financiero: {fecha_str}")
    
    # TARJETA GRANDE DE TOTAL
    st.metric("VENTA TOTAL BRUTA", formato_moneda_co(total_venta_dia), help="Suma de todos los medios de pago.")
    
    st.markdown("### 🧩 Desglose de Ingresos")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("💵 Efectivo", formato_moneda_co(ventas_efectivo))
    k2.metric("📱 Nequi / Transf.", formato_moneda_co(ventas_digital))
    k3.metric("💳 Tarjetas", formato_moneda_co(ventas_tarjeta))
    k4.metric("🛵 Apps/Otros", formato_moneda_co(ventas_apps))

    st.markdown("---")

    # --- PROFIT FIRST (Ahorro) ---
    st.subheader("💰 Fondo de Ahorro (Profit First)")
    col_pf1, col_pf2 = st.columns([1, 2])
    
    with col_pf1:
        porcentaje = st.number_input("% A Retener hoy", value=5, min_value=0, max_value=50)
    
    monto_profit = total_venta_dia * (porcentaje / 100)
    
    with col_pf2:
        st.info(f"👉 **ACCIÓN:** Transfiere **{formato_moneda_co(monto_profit)}** a tu cuenta de reservas.")
        confirmacion_ahorro = st.checkbox("✅ Confirmo que realicé la transferencia")

    st.markdown("---")

    # --- ARQUEO DE CAJA (Solo Efectivo) ---
    st.header("💵 Arqueo de Caja (Solo Billetes)")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("(+) Entran (Ventas Efec)", formato_moneda_co(ventas_efectivo))
    c2.metric("(-) Salen (Gastos/Compras)", formato_moneda_co(gastos_efectivo + compras_efectivo))
    c3.metric("(=) DEBE HABER EN CAJÓN", formato_moneda_co(saldo_teorico_cajon))
    
    col_real, col_diff = st.columns(2)
    saldo_real = col_real.number_input("¿Cuánto dinero contaste realmente?", min_value=0.0, step=500.0)
    diferencia = saldo_real - saldo_teorico_cajon
    
    with col_diff:
        st.write("### Diferencia:")
        if diferencia == 0:
            st.success(f"✅ CAJA CUADRADA PERFECTA ($ 0)")
        elif diferencia > 0:
            st.info(f"🔵 SOBRA DINERO: {formato_moneda_co(diferencia)}")
        else:
            st.error(f"🔴 FALTA DINERO: {formato_moneda_co(diferencia)}")

    # --- CIERRE FINAL ---
    st.markdown("---")
    notas = st.text_area("Notas del Cierre", placeholder="Ej: Sobró dinero porque no di una devuelta de 200 pesos...")
    
    if st.button("🔒 CERRAR CAJA Y GUARDAR", type="primary", use_container_width=True):
        estado_ahorro = "GUARDADO" if confirmacion_ahorro else "PENDIENTE"
        
        datos_cierre = [
            fecha_str,
            datetime.now(ZONA_HORARIA).strftime("%H:%M"),
            saldo_teorico_cajon,
            saldo_real,
            diferencia,
            ventas_digital, # Guardamos el total digital
            ventas_tarjeta,
            notas,
            monto_profit,
            estado_ahorro
        ]
        
        if guardar_cierre(sheet, datos_cierre):
            st.balloons()
            st.success("✅ Cierre Guardado Exitosamente.")
            time.sleep(2)
            st.rerun()