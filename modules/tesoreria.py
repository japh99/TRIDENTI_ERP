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

# --- FUNCIONES DE CARGA ---

def cargar_movimientos_dia(sheet, fecha_str):
    """Carga Ventas, Gastos y Compras para el arqueo del día."""
    try:
        # 1. Ventas
        ws_ventas = sheet.worksheet(HOJA_VENTAS)
        data_ventas = ws_ventas.get_all_records()
        df_ventas = pd.DataFrame(data_ventas)
        if not df_ventas.empty:
            df_ventas["Fecha"] = df_ventas["Fecha"].astype(str)
            df_ventas = df_ventas[df_ventas["Fecha"] == fecha_str]
            df_ventas["Total_Dinero"] = pd.to_numeric(df_ventas["Total_Dinero"], errors='coerce').fillna(0)
        
        # 2. Gastos
        try:
            ws_gastos = sheet.worksheet(HOJA_GASTOS)
            df_gastos = leer_datos_seguro(ws_gastos)
            if not df_gastos.empty:
                df_gastos["Fecha"] = df_gastos["Fecha"].astype(str)
                df_gastos = df_gastos[df_gastos["Fecha"] == fecha_str]
                df_gastos["Monto"] = pd.to_numeric(df_gastos["Monto"], errors='coerce').fillna(0)
        except: df_gastos = pd.DataFrame()

        # 3. Compras
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

def cargar_historial_completo(sheet):
    """Carga toda la hoja de cierres para los reportes históricos."""
    try:
        ws = sheet.worksheet(HOJA_CIERRES)
        df = leer_datos_seguro(ws)
        if not df.empty:
            # Convertir columnas numéricas
            cols_num = ["Saldo_Teorico_Efectivo", "Saldo_Real_Contado", "Diferencia", "Profit_Retenido"]
            for c in cols_num:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
            
            # Ordenar por fecha descendente
            if "Fecha" in df.columns:
                df = df.sort_values("Fecha", ascending=False)
        return df
    except: return pd.DataFrame()

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
    except Exception as e:
        st.error(f"Error guardando: {e}")
        return False

# --- INTERFAZ ---
def show(sheet):
    st.title("🔐 Tesorería Central")
    st.caption("Control de Caja, Auditoría y Fondo de Ahorro.")
    st.markdown("---")
    
    if not sheet: return

    # TABS ORGANIZADOS
    tab_cierre, tab_historial, tab_ahorro = st.tabs(["📝 CIERRE DEL DÍA", "📜 HISTORIAL DE CAJA", "🐷 BANCO DE AHORRO"])

    # ==========================================
    # TAB 1: EL FORMULARIO DE CIERRE (DIARIO)
    # ==========================================
    with tab_cierre:
        hoy = datetime.now(ZONA_HORARIA).date()
        c_f, _ = st.columns([1, 2])
        fecha_cierre = c_f.date_input("Fecha de Arqueo", value=hoy)
        fecha_str = fecha_cierre.strftime("%Y-%m-%d")

        # Verificar si ya existe cierre
        df_hist = cargar_historial_completo(sheet)
        ya_cerrado = False
        if not df_hist.empty and "Fecha" in df_hist.columns:
            if fecha_str in df_hist["Fecha"].astype(str).values:
                ya_cerrado = True

        if ya_cerrado:
            st.success(f"✅ La caja del {fecha_str} ya fue cerrada.")
            st.info("Ve a la pestaña '📜 HISTORIAL DE CAJA' para ver los detalles.")
        else:
            # LÓGICA DE CIERRE ACTIVO
            df_ventas, df_gastos, df_compras, ws_ventas = cargar_movimientos_dia(sheet, fecha_str)

            if df_ventas is None or df_ventas.empty:
                st.warning("⚠️ No hay ventas registradas. Descarga ventas primero.")
            else:
                # 1. AUDITORÍA
                with st.expander("🛠️ Paso 1: Auditoría (Corregir Nequi/Efectivo)", expanded=False):
                    df_audit = df_ventas[["Hora", "Numero_Recibo", "Total_Dinero", "Metodo_Pago_Loyverse", "Metodo_Pago_Real_Auditado"]].drop_duplicates(subset=["Numero_Recibo"])
                    df_edit = st.data_editor(
                        df_audit,
                        column_config={"Metodo_Pago_Real_Auditado": st.column_config.SelectboxColumn("MÉTODO REAL", options=["Efectivo", "Nequi", "Tarjeta", "Rappi", "Otro"], required=True)},
                        hide_index=True, use_container_width=True, key="audit_table"
                    )
                    if st.button("💾 Guardar Correcciones"):
                        if actualizar_metodos_pago(ws_ventas, df_edit):
                            st.success("✅ Corregido."); time.sleep(1); st.rerun()

                # 2. CÁLCULOS
                v_total = df_ventas["Total_Dinero"].sum()
                v_efec = df_ventas[df_ventas["Metodo_Pago_Real_Auditado"] == "Efectivo"]["Total_Dinero"].sum()
                v_digi = df_ventas[df_ventas["Metodo_Pago_Real_Auditado"].str.contains("Nequi|Davi|Banco|Transf", case=False, na=False)]["Total_Dinero"].sum()
                v_tarj = df_ventas[df_ventas["Metodo_Pago_Real_Auditado"].isin(["Tarjeta", "Datafono"])]["Total_Dinero"].sum()
                
                g_efec = df_gastos[df_gastos["Metodo_Pago"].str.contains("Efectivo", case=False)]["Monto"].sum() if not df_gastos.empty else 0
                c_efec = df_compras[df_compras["Metodo_Pago"].str.contains("Efectivo", case=False)]["Precio_Total_Pagado"].sum() if not df_compras.empty and "Metodo_Pago" in df_compras.columns else 0

                saldo_teorico = v_efec - g_efec - c_efec

                # 3. RESUMEN
                st.markdown("---")
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("💰 VENTA TOTAL", formato_moneda_co(v_total))
                k2.metric("💵 Efectivo", formato_moneda_co(v_efec))
                k3.metric("📱 Digital", formato_moneda_co(v_digi))
                k4.metric("💳 Tarjeta", formato_moneda_co(v_tarj))

                # 4. PROFIT FIRST
                st.markdown("---")
                st.subheader("💰 Fondo de Ahorro (Profit First)")
                c_p1, c_p2 = st.columns([1, 2])
                porc = c_p1.number_input("% Retención", value=5, min_value=1, max_value=50)
                monto_p = v_total * (porc/100)
                c_p2.info(f"👉 Transfiere: **{formato_moneda_co(monto_p)}**")
                check_ahorro = c_p2.checkbox("✅ Confirmo transferencia")

                # 5. ARQUEO
                st.markdown("---")
                st.subheader("💵 Arqueo de Caja")
                c1, c2, c3 = st.columns(3)
                c1.metric("(+) Entradas", formato_moneda_co(v_efec))
                c2.metric("(-) Salidas", formato_moneda_co(g_efec + c_efectivo))
                c3.metric("(=) TEÓRICO", formato_moneda_co(saldo_teorico))
                
                col_r, col_d = st.columns(2)
                real = col_r.number_input("¿Cuánto contaste?", min_value=0.0, step=500.0)
                diff = real - saldo_teorico
                
                with col_d:
                    if diff == 0: st.success("✅ CUADRADO")
                    elif diff > 0: st.info(f"🔵 SOBRA: {formato_moneda_co(diff)}")
                    else: st.error(f"🔴 FALTA: {formato_moneda_co(diff)}")

                notas = st.text_area("Notas del Cierre")
                
                if st.button("🔒 CERRAR CAJA Y GUARDAR", type="primary", use_container_width=True):
                    estado_ahorro = "GUARDADO" if check_ahorro else "PENDIENTE"
                    datos = [
                        fecha_str, datetime.now(ZONA_HORARIA).strftime("%H:%M"),
                        float(saldo_teorico), float(real), float(diff),
                        float(v_digi), float(v_tarj), str(notas), float(monto_p), estado_ahorro
                    ]
                    if guardar_cierre(sheet, datos):
                        st.balloons()
                        st.success("✅ Cierre Guardado.")
                        time.sleep(2); st.rerun()

    # ==========================================
    # TAB 2: HISTORIAL DE CIERRES
    # ==========================================
    with tab_historial:
        st.subheader("📜 Bitácora de Cierres de Caja")
        
        df_h = cargar_historial_completo(sheet)
        if not df_h.empty:
            # KPIs Generales
            diferencia_total = df_h["Diferencia"].sum()
            
            # Mostrar Resumen
            if diferencia_total < 0:
                st.error(f"🔴 Descuadre Acumulado Histórico: {formato_moneda_co(diferencia_total)}")
            else:
                st.success(f"🔵 Sobrante Acumulado Histórico: {formato_moneda_co(diferencia_total)}")
            
            # Tabla Bonita
            df_show = df_h.copy()
            # Formatos visuales
            for c in ["Saldo_Teorico_Efectivo", "Saldo_Real_Contado", "Diferencia"]:
                df_show[c] = df_show[c].apply(formato_moneda_co)
            
            st.dataframe(
                df_show[["Fecha", "Hora_Cierre", "Saldo_Teorico_Efectivo", "Saldo_Real_Contado", "Diferencia", "Notas"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Diferencia": st.column_config.TextColumn("Cuadre", help="Rojo: Falta, Azul: Sobra"),
                    "Notas": st.column_config.TextColumn("Observaciones", width="large")
                }
            )
        else:
            st.info("No hay historial disponible.")

    # ==========================================
    # TAB 3: BANCO DE AHORRO (PROFIT FIRST)
    # ==========================================
    with tab_ahorro:
        st.subheader("🐷 Fondo de Reservas (Profit First)")
        st.caption("Dinero acumulado para reparto de utilidades o emergencias.")
        
        df_h = cargar_historial_completo(sheet)
        if not df_h.empty:
            # Filtrar solo lo GUARDADO
            if "Estado_Ahorro" in df_h.columns:
                ahorro_real = df_h[df_h["Estado_Ahorro"] == "GUARDADO"]["Profit_Retenido"].sum()
                ahorro_pendiente = df_h[df_h["Estado_Ahorro"] == "PENDIENTE"]["Profit_Retenido"].sum()
            else:
                ahorro_real = 0
                ahorro_pendiente = 0
            
            # Tarjetas Grandes
            col_a, col_b = st.columns(2)
            col_a.metric("💰 Total en el Banco (Ahorrado)", formato_moneda_co(ahorro_real))
            col_b.metric("⚠️ Pendiente por Transferir", formato_moneda_co(ahorro_pendiente), delta_color="inverse")
            
            st.markdown("---")
            st.write("#### 📅 Detalle de Aportes")
            
            # Tabla de Ahorros
            if "Profit_Retenido" in df_h.columns:
                df_ahorro = df_h[df_h["Profit_Retenido"] > 0].copy()
                df_ahorro["Monto"] = df_ahorro["Profit_Retenido"].apply(formato_moneda_co)
                
                st.dataframe(
                    df_ahorro[["Fecha", "Monto", "Estado_Ahorro", "Notas"]],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Estado_Ahorro": st.column_config.Column(
                            "Estado",
                            help="GUARDADO = Ya se transfirió al banco",
                            width="medium"
                        )
                    }
                )
        else:
            st.info("Aún no has iniciado tu fondo de ahorro.")
