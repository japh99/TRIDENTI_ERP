import streamlit as st
import pandas as pd
from datetime import datetime
import time
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero, generar_id

# --- CONFIGURACIÓN DE HOJAS ---
HOJA_CIERRES = "LOG_CIERRES_CAJA"
HOJA_ABONOS = "LOG_ABONOS_PROFIT"
HOJA_RETIROS = "LOG_RETIROS_PROFIT"

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

def show(sheet):
    st.title("🐷 Banco Profit (Ahorro Real)")
    st.caption("Gestiona el dinero físico reservado de tus ventas y tus retiros de utilidad.")

    # 1. CARGA DE DATOS SEGURO
    try:
        ws_cierres = sheet.worksheet(HOJA_CIERRES)
        df_c = leer_datos_seguro(ws_cierres)
        
        ws_abonos = sheet.worksheet(HOJA_ABONOS)
        df_a = leer_datos_seguro(ws_abonos)
        
        ws_retiros = sheet.worksheet(HOJA_RETIROS)
        df_r = leer_datos_seguro(ws_retiros)
        
        # Validación de columna crítica para evitar KeyError
        col_profit = "Profit_Retenido"
        if not df_c.empty and col_profit not in df_c.columns:
            st.error(f"⚠️ Error de base de datos: No se encuentra la columna '{col_profit}'.")
            return
    except Exception as e:
        st.error(f"Error cargando bases de datos del banco: {e}")
        return

    # --- 2. PROCESAMIENTO DE SALDOS ---
    # Limpieza de números
    if not df_c.empty:
        df_c[col_profit] = pd.to_numeric(df_c[col_profit], errors='coerce').fillna(0)
        df_c["Estado_Ahorro"] = df_c["Estado_Ahorro"].astype(str).str.strip()
    
    if not df_a.empty:
        df_a["Monto_Abonado"] = pd.to_numeric(df_a["Monto_Abonado"], errors='coerce').fillna(0)
    
    if not df_r.empty:
        df_r["Monto_Retirado"] = pd.to_numeric(df_r["Monto_Retirado"], errors='coerce').fillna(0)

    # Cálculos
    ahorro_real_confirmado = df_a["Monto_Abonado"].sum() if not df_a.empty else 0
    retiros_totales = df_r["Monto_Retirado"].sum() if not df_r.empty else 0
    saldo_disponible = ahorro_real_confirmado - retiros_totales

    # Dinero que Tesorería ya calculó pero que aún no has confirmado (Pendiente)
    pendientes = df_c[df_c["Estado_Ahorro"] == "Pendiente"].copy() if not df_c.empty else pd.DataFrame()
    monto_pendiente = pendientes[col_profit].sum() if not pendientes.empty else 0

    # --- DASHBOARD PRINCIPAL ---
    c1, c2, c3 = st.columns(3)
    c1.metric("💰 Saldo Real Disponible", formato_moneda(saldo_disponible), help="Dinero que ya confirmaste haber guardado menos retiros.")
    c2.metric("⚠️ Pendiente por Confirmar", formato_moneda(monto_pendiente), help="Dinero de cierres auditados que aún no has metido al banco.")
    c3.metric("💸 Total Retirado", formato_moneda(retiros_totales))

    st.markdown("---")
    t1, t2, t3 = st.tabs(["📥 CONFIRMAR INGRESO", "📤 REGISTRAR RETIRO", "📜 HISTORIAL COMPLETO"])

    with t1:
        st.subheader("Confirmar dinero físico ingresado")
        if not pendientes.empty:
            st.info(f"Tienes {len(pendientes)} cierres de caja esperando por ser guardados en el fondo.")
            
            # Crear lista amigable para seleccionar
            opciones = pendientes.apply(
                lambda x: f"{x['Fecha']} | Sugerido: {formato_moneda(x[col_profit])} | ID: {str(x['Numero_Cierre_Loyverse'])[:8]}", 
                axis=1
            ).tolist()
            
            seleccion = st.selectbox("¿Qué ahorro vas a guardar físicamente ahora?", opciones)
            
            # Recuperar datos del registro seleccionado
            idx_sel = opciones.index(seleccion)
            fila_c = pendientes.iloc[idx_sel]
            
            ca, cb = st.columns(2)
            monto_real = ca.number_input("Monto real ingresado:", value=float(fila_c[col_profit]), step=1000.0)
            responsable = cb.text_input("Responsable del depósito:", value="Admin")

            if st.button("✅ CONFIRMAR INGRESO DE DINERO", type="primary", use_container_width=True):
                # 1. Registrar el abono en LOG_ABONOS_PROFIT
                # Estructura: ID, Fecha, Hora, Fecha_Cierre_O, Monto_Abonado, Responsable
                datos_abono = [
                    generar_id(),
                    datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d"),
                    datetime.now(ZONA_HORARIA).strftime("%H:%M"),
                    fila_c["Fecha"],
                    monto_real,
                    responsable
                ]
                
                # 2. Actualizar el estado en LOG_CIERRES_CAJA (para que ya no sea Pendiente)
                try:
                    # Buscamos la fila correcta en el Excel por el ID de Loyverse (Columna K / 11)
                    ids_en_excel = ws_cierres.col_values(11) 
                    target_id = str(fila_c["Numero_Cierre_Loyverse"])
                    
                    if target_id in ids_en_excel:
                        row_num = ids_en_excel.index(target_id) + 1
                        # Actualizamos la columna J (Estado_Ahorro / Columna 10)
                        ws_cierres.update_cell(row_num, 10, "Ahorrado")
                        
                        # Guardamos el abono
                        ws_abonos.append_row(datos_abono)
                        
                        st.balloons()
                        st.success("¡Ingreso confirmado! El saldo disponible ha sido actualizado.")
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error("No se encontró el registro original en el Excel para actualizar.")
                except Exception as e:
                    st.error(f"Error al sincronizar con el Excel: {e}")
        else:
            st.success("🎉 ¡Excelente! No tienes ahorros pendientes por confirmar.")

    with t2:
        st.subheader("Registrar salida de dinero del fondo")
        st.warning("Usa esta sección solo si vas a sacar dinero del ahorro para gastos o utilidades.")
        
        c_r1, c_r2 = st.columns(2)
        m_ret = c_r1.number_input("Monto a retirar:", min_value=0.0, step=5000.0)
        motivo = c_r2.text_input("Motivo del retiro:", placeholder="Ej: Pago de impuestos, utilidad socios...")
        resp_r = st.text_input("Persona que retira el dinero:", key="banco_resp_r")
        
        if st.button("🚨 EJECUTAR RETIRO", type="primary", use_container_width=True):
            if 0 < m_ret <= saldo_disponible:
                if motivo and resp_r:
                    # Estructura LOG_RETIROS_PROFIT: ID, Fecha, Hora, Monto_Retirado, Motivo, Responsable
                    datos_r = [
                        generar_id(),
                        datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d"),
                        datetime.now(ZONA_HORARIA).strftime("%H:%M"),
                        m_ret,
                        motivo,
                        resp_r
                    ]
                    ws_retiros.append_row(datos_r)
                    st.success("Retiro registrado exitosamente.")
                    time.sleep(1.5)
                    st.rerun()
                else:
                    st.warning("Completa el motivo y el responsable.")
            else:
                st.error(f"Fondos insuficientes. El saldo real es {formato_moneda(saldo_disponible)}")

    with t3:
        st.subheader("Historial de Entradas y Salidas")
        
        # Crear un historial unificado para la vista
        h_entradas = pd.DataFrame()
        if not df_a.empty:
            h_entradas = df_a[["Fecha", "Monto_Abonado", "Responsable"]].copy()
            h_entradas.columns = ["Fecha", "Monto", "Responsable"]
            h_entradas["Tipo"] = "ENTRADA (Ahorro)"
            h_entradas["Detalle"] = "Ingreso de Cierre"

        h_salidas = pd.DataFrame()
        if not df_r.empty:
            h_salidas = df_r[["Fecha", "Monto_Retirado", "Motivo", "Responsable"]].copy()
            h_salidas.columns = ["Fecha", "Monto", "Detalle", "Responsable"]
            h_salidas["Tipo"] = "SALIDA (Retiro)"

        # Combinar ambos si hay datos
        if not h_entradas.empty or not h_salidas.empty:
            historial = pd.concat([h_entradas, h_salidas]).sort_values("Fecha", ascending=False)
            
            # Formato moneda para la tabla
            hist_view = historial.copy()
            hist_view["Monto"] = hist_view["Monto"].apply(formato_moneda)
            
            def color_mov(v):
                return 'color: green; font-weight: bold' if "ENTRADA" in v else 'color: red; font-weight: bold'

            st.dataframe(
                hist_view[["Fecha", "Tipo", "Monto", "Detalle", "Responsable"]]
                .style.applymap(color_mov, subset=["Tipo"]),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Aún no hay movimientos registrados en el banco.")
