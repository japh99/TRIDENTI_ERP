import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero, generar_id

# --- CONFIGURACIÓN DE HOJAS ---
HOJA_VENTAS = "LOG_VENTAS_LOYVERSE"
HOJA_GASTOS = "LOG_GASTOS"
HOJA_CIERRES = "LOG_CIERRES_CAJA"

# Encabezados de la Base de Datos de Cierres
HEADERS_CIERRE = [
    "Fecha_Cierre", "Hora_Cierre", "Saldo_Teorico_E", "Saldo_Real_Cor", 
    "Diferencia", "Total_Nequi", "Total_Tarjetas", "Ticket_Ini", "Ticket_Fin",
    "Profit_Retenido", "Estado_Ahorro", "Numero_Cierre_Loyverse", "Shift_ID"
]

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

# --- BACKEND: CARGA DE DATOS ---

def cargar_turnos_disponibles(sheet):
    """Agrupa las ventas descargadas por Shift_ID (Turno de Loyverse)."""
    try:
        ws_v = sheet.worksheet(HOJA_VENTAS)
        df_v = leer_datos_seguro(ws_v)
        if df_v.empty: return pd.DataFrame()

        # Asegurar números
        df_v["Total_Dinero"] = pd.to_numeric(df_v["Total_Dinero"], errors='coerce').fillna(0)
        
        # Agrupar por Shift_ID (Concepto real de cierre en Loyverse)
        # Si no hay Shift_ID, agrupamos por Fecha para compatibilidad
        agrupador = "Shift_ID" if "Shift_ID" in df_v.columns else "Fecha"
        
        df_shifts = df_v.groupby(agrupador).agg({
            "Fecha": "first",
            "Hora": ["min", "max"],
            "Total_Dinero": "sum",
            "Numero_Recibo": ["min", "max"]
        }).reset_index()
        
        # Aplanar nombres de columnas
        df_shifts.columns = [agrupador, "Fecha", "Hora_Apertura", "Hora_Cierre", "Venta_Total", "Ticket_Ini", "Ticket_Fin"]
        return df_shifts.sort_values("Fecha", ascending=False)
    except: return pd.DataFrame()

def obtener_tickets_de_turno(sheet, shift_id):
    """Trae los tickets individuales de un turno específico."""
    try:
        ws_v = sheet.worksheet(HOJA_VENTAS)
        df_v = leer_datos_seguro(ws_v)
        agrupador = "Shift_ID" if "Shift_ID" in df_v.columns else "Fecha"
        
        df_turno = df_v[df_v[agrupador] == shift_id].copy()
        df_turno["Total_Dinero"] = pd.to_numeric(df_turno["Total_Dinero"], errors='coerce').fillna(0)
        
        # Consolidar productos en tickets únicos
        df_tickets = df_turno.groupby("Numero_Recibo").agg({
            "Hora": "first",
            "Total_Dinero": "sum",
            "Metodo_Pago_Loyverse": "first"
        }).reset_index().sort_values("Hora")
        
        return df_tickets
    except: return pd.DataFrame()

# --- INTERFAZ PRINCIPAL ---

def show(sheet):
    st.title("🔐 Tesorería & Auditoría")
    st.caption("Procesa cierres basados en los turnos sincronizados de Loyverse.")
    
    if not sheet: return

    tab1, tab2 = st.tabs(["📝 PROCESAR NUEVO CIERRE", "📜 CONSULTAR CIERRES PASADOS"])

    with tab1:
        st.subheader("Selección de Turno a Cerrar")
        df_shifts = cargar_turnos_disponibles(sheet)

        if df_shifts.empty:
            st.warning("No hay ventas descargadas. Ve al módulo de **Ventas** para sincronizar con Loyverse.")
            return

        # Crear etiquetas para el selector
        df_shifts["Label"] = df_shifts.apply(
            lambda x: f"Día: {x['Fecha']} | Venta: {formato_moneda(x['Venta_Total'])} | Tickets: {x['Ticket_Ini']} a {x['Ticket_Fin']}", 
            axis=1
        )
        
        seleccion = st.selectbox("Turnos detectados en el sistema:", df_shifts["Label"].tolist())
        shift_data = df_shifts[df_shifts["Label"] == seleccion].iloc[0]
        id_turno = shift_data["Shift_ID"] if "Shift_ID" in shift_data else shift_data["Fecha"]

        st.markdown("---")
        
        # CARGAR TICKETS DEL TURNO
        df_tickets = obtener_tickets_de_turno(sheet, id_turno)
        
        with st.expander("🛠️ Auditoría de Pagos (Desglose Mixto)", expanded=True):
            st.write("Si una cuenta fue pagada con dos métodos, ajusta los valores aquí.")
            
            # Preparar columnas para el editor
            df_tickets["Efectivo_Real"] = df_tickets.apply(lambda x: x["Total_Dinero"] if x["Metodo_Pago_Loyverse"] == "Efectivo" else 0.0, axis=1)
            df_tickets["Nequi_Real"] = df_tickets.apply(lambda x: x["Total_Dinero"] if "Nequi" in str(x["Metodo_Pago_Loyverse"]) else 0.0, axis=1)
            df_tickets["Tarjeta_Real"] = df_tickets.apply(lambda x: x["Total_Dinero"] if "Tarjeta" in str(x["Metodo_Pago_Loyverse"]) else 0.0, axis=1)
            df_tickets["Suma"] = df_tickets["Efectivo_Real"] + df_tickets["Nequi_Real"] + df_tickets["Tarjeta_Real"]

            df_ed = st.data_editor(
                df_tickets[["Numero_Recibo", "Hora", "Total_Dinero", "Efectivo_Real", "Nequi_Real", "Tarjeta_Real", "Suma"]],
                column_config={
                    "Total_Dinero": st.column_config.NumberColumn("Total Ticket", format="$%d", disabled=True),
                    "Efectivo_Real": st.column_config.NumberColumn("Efectivo $", format="$%d"),
                    "Nequi_Real": st.column_config.NumberColumn("Nequi $", format="$%d"),
                    "Tarjeta_Real": st.column_config.NumberColumn("Tarjeta $", format="$%d"),
                    "Suma": st.column_config.NumberColumn("Validación", format="$%d", disabled=True),
                },
                hide_index=True, use_container_width=True, key="editor_teso_mixto"
            )
            
            # Validación de sumas
            error_check = abs(df_ed["Total_Dinero"] - df_ed["Suma"]).sum()
            if error_check > 1:
                st.error("🚨 La repartición de los pagos no coincide con el total de la venta.")

        # RESULTADOS DEL TURNO
        v_total = df_ed["Total_Dinero"].sum()
        v_efec = df_ed["Efectivo_Real"].sum()
        v_digital = df_ed["Nequi_Real"].sum() + df_ed["Tarjeta_Real"].sum()

        st.markdown("#### 📊 Resumen Financiero")
        c1, c2, c3 = st.columns(3)
        c1.metric("Venta Bruta Turno", formato_moneda(v_total))
        c2.metric("Efectivo Esperado", formato_moneda(v_efec))
        c3.metric("Nequi / Tarjetas", formato_moneda(v_digital))

        st.markdown("---")
        st.markdown("#### 💵 Arqueo Físico")
        real = st.number_input("¿Cuánto efectivo contaste físicamente?", min_value=0.0, step=500.0)
        z_rep = st.text_input("Z-Report / Número de Cierre")
        
        diff = real - v_efec
        if diff == 0: st.success("✅ CAJA CUADRADA")
        elif diff > 0: st.info(f"### 🔵 SOBRANTE: {formato_moneda(diff)}")
        else: st.error(f"### 🔴 FALTANTE: {formato_moneda(diff)}")

        if st.button("🔒 GUARDAR CIERRE DEFINITIVO", type="primary", use_container_width=True):
            if error_check > 1:
                st.warning("Corrige los tickets en rojo antes de guardar.")
            elif not z_rep:
                st.warning("Debes ingresar un identificador de cierre (Z-Report).")
            else:
                datos = {
                    "Fecha_Cierre": shift_data["Fecha"],
                    "Hora_Cierre": datetime.now(ZONA_HORARIA).strftime("%H:%M"),
                    "Saldo_Teorico_E": v_efec,
                    "Saldo_Real_Cor": real,
                    "Diferencia": diff,
                    "Total_Nequi": df_ed["Nequi_Real"].sum(),
                    "Total_Tarjetas": df_ed["Tarjeta_Real"].sum(),
                    "Ticket_Ini": shift_data["Ticket_Ini"],
                    "Ticket_Fin": shift_data["Ticket_Fin"],
                    "Profit_Retenido": v_total * 0.05,
                    "Estado_Ahorro": "Pendiente",
                    "Numero_Cierre_Loyverse": z_rep,
                    "Shift_ID": str(id_turno)
                }
                ws_c = sheet.worksheet(HOJA_CIERRES)
                ws_c.append_row([str(datos.get(h, "")) for h in HEADERS_CIERRE])
                st.balloons(); time.sleep(1); st.rerun()

    with tab2:
        st.subheader("Historial de Cierres")
        fecha_h = st.date_input("Filtrar por fecha:", value=datetime.now(ZONA_HORARIA).date())
        
        try:
            ws_h = sheet.worksheet(HOJA_CIERRES)
            df_h = leer_datos_seguro(ws_h)
            if not df_h.empty:
                df_h.columns = df_h.columns.str.strip()
                # Filtrar
                df_res = df_h[df_h["Fecha_Cierre"] == str(fecha_h)].copy()
                
                if df_res.empty:
                    st.info(f"No hay cierres registrados el {fecha_h}")
                else:
                    for c in ["Saldo_Teorico_E", "Saldo_Real_Cor", "Diferencia"]:
                        df_res[c] = pd.to_numeric(df_res[c], errors='coerce').apply(formato_moneda)
                    st.dataframe(df_res, use_container_width=True, hide_index=True)
            else:
                st.write("Base de datos de cierres vacía.")
        except: pass
