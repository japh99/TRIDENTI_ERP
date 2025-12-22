import streamlit as st
import pandas as pd
from datetime import datetime
import time
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero, generar_id

# --- CONFIGURACIÓN DE HOJAS ---
HOJA_VENTAS = "LOG_VENTAS_LOYVERSE"
HOJA_GASTOS = "LOG_GASTOS"
HOJA_CIERRES = "LOG_CIERRES_CAJA"

# Encabezados de la Base de Datos de Cierres (Actualizados)
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
    """Agrupa las ventas descargadas por Shift_ID respetando la fecha de apertura."""
    try:
        ws_v = sheet.worksheet(HOJA_VENTAS)
        df_v = leer_datos_seguro(ws_v)
        if df_v.empty: return pd.DataFrame()

        # Asegurar tipos de datos
        df_v["Total_Dinero"] = pd.to_numeric(df_v["Total_Dinero"], errors='coerce').fillna(0)
        df_v["TS"] = pd.to_datetime(df_v["Fecha"] + " " + df_v["Hora"], errors='coerce')
        
        # Agrupamos por Shift_ID (ID de Loyverse)
        agrupador = "Shift_ID" if "Shift_ID" in df_v.columns else "Fecha"
        
        df_shifts = df_v.groupby(agrupador).agg(
            Fecha_Apertura=("Fecha", "min"), # Tomamos la fecha mínima (Día de inicio del turno)
            Hora_Apertura=("Hora", "min"),
            Hora_Cierre=("Hora", "max"),
            Venta_Total=("Total_Dinero", "sum"),
            Ticket_Ini=("Numero_Recibo", "min"),
            Ticket_Fin=("Numero_Recibo", "max"),
            Total_Recibos=("Numero_Recibo", "nunique"),
            TS_Ref=("TS", "min")
        ).reset_index()
        
        # Ordenar por tiempo real de apertura (lo más nuevo arriba)
        return df_shifts.sort_values("TS_Ref", ascending=False)
    except Exception as e:
        st.error(f"Error cargando turnos: {e}")
        return pd.DataFrame()

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

# --- INTERFAZ ---

def show(sheet):
    st.title("🔐 Tesorería & Auditoría")
    st.caption("Cierres de caja sincronizados por jornada operativa.")
    
    if not sheet: return

    tab1, tab2 = st.tabs(["📝 PROCESAR NUEVO CIERRE", "📜 CONSULTAR CIERRES PASADOS"])

    with tab1:
        st.subheader("Selección de Turno Detectado")
        df_shifts = cargar_turnos_disponibles(sheet)

        if df_shifts.empty:
            st.warning("No hay ventas sincronizadas. Ve al módulo de **Ventas**.")
            return

        # --- LÓGICA DE ETIQUETA CORREGIDA ---
        # Ahora el selector muestra la fecha en que se ABRIÓ el turno
        df_shifts["Label"] = df_shifts.apply(
            lambda x: f"Jornada: {x['Fecha_Apertura']} | Tickets: {x['Ticket_Ini']} a {x['Ticket_Fin']} | Total: {formato_moneda(x['Venta_Total'])}", 
            axis=1
        )
        
        seleccion = st.selectbox("Selecciona la jornada que vas a cerrar:", df_shifts["Label"].tolist())
        shift_data = df_shifts[df_shifts["Label"] == seleccion].iloc[0]
        id_turno = shift_data["Shift_ID"] if "Shift_ID" in shift_data else shift_data["Fecha_Apertura"]

        st.markdown("---")
        
        # CARGAR TICKETS DEL TURNO
        df_tickets = obtener_tickets_de_turno(sheet, id_turno)
        
        with st.expander("🛠️ Auditoría de Pagos (Corregir errores de cajero)", expanded=True):
            # Inicializar columnas reales
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
                hide_index=True, use_container_width=True, key="editor_teso_turno_v2"
            )
            
            error_check = abs(df_ed["Total_Dinero"] - df_ed["Suma"]).sum()
            if error_check > 1:
                st.error("🚨 El desglose no coincide con el total. Verifica los tickets en rojo.")

        # RESULTADOS
        v_total = df_ed["Total_Dinero"].sum()
        v_efec = df_ed["Efectivo_Real"].sum()
        v_digital = df_ed["Nequi_Real"].sum() + df_ed["Tarjeta_Real"].sum()

        st.markdown("#### 📊 Resumen Auditado")
        k1, k2, k3 = st.columns(3)
        k1.metric("Venta Bruta", formato_moneda(v_total))
        k2.metric("Efectivo en Turno", formato_moneda(v_efec))
        k3.metric("Digital / Nequi", formato_moneda(v_digital))

        st.markdown("---")
        st.markdown("#### 💵 Arqueo de Efectivo")
        real = st.number_input("¿Cuánto efectivo contaste físicamente?", min_value=0.0, step=500.0)
        z_rep = st.text_input("Número de Z-Report / Cierre")
        
        diff = real - v_efec
        if diff == 0: st.success("✅ CAJA CUADRADA")
        elif diff > 0: st.info(f"🔵 SOBRANTE: {formato_moneda(diff)}")
        else: st.error(f"### 🔴 FALTANTE: {formato_moneda(diff)}")

        # --- SECCIÓN DE PROFIT (AHORRO) ---
        st.markdown("---")
        pct_ahorro = st.slider("% Ahorro Sugerido (Profit First)", 1, 15, 5)
        monto_ahorro = v_total * (pct_ahorro / 100)
        st.info(f"💡 **Ahorro para el Banco Profit:** {formato_moneda(monto_ahorro)}")

        notas = st.text_area("Notas del Cierre")

        if st.button("🔒 GUARDAR CIERRE Y REGISTRAR AHORRO", type="primary", use_container_width=True):
            if error_check > 1:
                st.warning("No puedes guardar si los tickets no están cuadrados.")
            elif not z_rep:
                st.warning("Ingresa el número de Z-Report.")
            else:
                datos_finales = {
                    "Fecha_Cierre": shift_data["Fecha_Apertura"], # GUARDAMOS CON LA FECHA DE APERTURA (Día contable)
                    "Hora_Cierre": datetime.now(ZONA_HORARIA).strftime("%H:%M"),
                    "Saldo_Teorico_E": v_efec,
                    "Saldo_Real_Cor": real,
                    "Diferencia": diff,
                    "Total_Nequi": df_ed["Nequi_Real"].sum(),
                    "Total_Tarjetas": df_ed["Tarjeta_Real"].sum(),
                    "Ticket_Ini": shift_data["Ticket_Ini"],
                    "Ticket_Fin": shift_data["Ticket_Fin"],
                    "Profit_Retenido": monto_ahorro, # REGISTRAMOS EL PROFIT AQUÍ
                    "Estado_Ahorro": "Pendiente",
                    "Numero_Cierre_Loyverse": z_rep,
                    "Shift_ID": str(id_turno)
                }
                ws_c = sheet.worksheet(HOJA_CIERRES)
                ws_c.append_row([str(datos_finales.get(h, "")) for h in HEADERS_CIERRE])
                st.balloons(); time.sleep(1); st.rerun()

    with tab2:
        st.subheader("Historial de Cierres")
        if st.button("🔄 RECARGAR HISTORIAL"):
            st.cache_data.clear(); st.rerun()
            
        try:
            df_h = leer_datos_seguro(sheet.worksheet(HOJA_CIERRES))
            if not df_h.empty:
                df_h.columns = df_h.columns.str.strip()
                df_h = df_h.sort_values("Fecha_Cierre", ascending=False).head(20)
                
                # Formatear montos para la tabla
                for c in ["Saldo_Teorico_E", "Saldo_Real_Cor", "Diferencia", "Profit_Retenido"]:
                    if c in df_h.columns:
                        df_h[c] = pd.to_numeric(df_h[c], errors='coerce').apply(formato_moneda)
                
                st.dataframe(df_h, use_container_width=True, hide_index=True)
            else:
                st.info("Sin historial.")
        except: pass
