import streamlit as st
import pandas as pd
from datetime import datetime
import time
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero, generar_id

# --- CONFIGURACIÓN DE HOJAS ---
HOJA_VENTAS = "LOG_VENTAS_LOYVERSE"
HOJA_GASTOS = "LOG_GASTOS"
HOJA_CIERRES = "LOG_CIERRES_CAJA"

# Encabezados Estándar
HEADERS_CIERRE = [
    "Fecha", "Hora_Cierre", "Saldo_Teorico_E", "Saldo_Real_Cor", 
    "Diferencia", "Total_Nequi", "Total_Tarjetas", "Notas", 
    "Profit_Retenido", "Estado_Ahorro", "Numero_Cierre_Loyverse"
]

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

# --- FUNCIONES DE CARGA ---

def cargar_movimientos_desglosados(sheet, fecha_str):
    try:
        ws_v = sheet.worksheet(HOJA_VENTAS)
        df_raw = leer_datos_seguro(ws_v)
        
        if not df_raw.empty:
            df_raw["Fecha"] = df_raw["Fecha"].astype(str)
            df_dia = df_raw[df_raw["Fecha"] == fecha_str].copy()
            df_dia["Total_Dinero"] = pd.to_numeric(df_dia["Total_Dinero"], errors='coerce').fillna(0)
            
            # Agrupar por Recibo
            df_grouped = df_dia.groupby("Numero_Recibo").agg({
                "Total_Dinero": "sum",
                "Metodo_Pago_Loyverse": "first",
                "Hora": "first"
            }).reset_index()

            # Inicializar desglose
            df_grouped["Efectivo_Real"] = df_grouped.apply(lambda x: x["Total_Dinero"] if x["Metodo_Pago_Loyverse"] == "Efectivo" else 0.0, axis=1)
            df_grouped["Nequi_Real"] = df_grouped.apply(lambda x: x["Total_Dinero"] if "Nequi" in str(x["Metodo_Pago_Loyverse"]) else 0.0, axis=1)
            df_grouped["Tarjeta_Real"] = df_grouped.apply(lambda x: x["Total_Dinero"] if "Tarjeta" in str(x["Metodo_Pago_Loyverse"]) else 0.0, axis=1)
            
            return df_grouped, ws_v
        return pd.DataFrame(), None
    except Exception as e:
        st.error(f"Error cargando ventas: {e}")
        return None, None

# --- INTERFAZ ---

def show(sheet):
    st.title("🔐 Tesorería: Cierre de Caja")
    
    if not sheet: return

    # CREAR PESTAÑAS PARA ORDENAR EL HISTORIAL
    tab_cierre, tab_historial = st.tabs(["📝 PROCESAR CIERRE", "📜 HISTORIAL DE CIERRES"])

    hoy = datetime.now(ZONA_HORARIA).date()
    
    with tab_cierre:
        fecha_cierre = st.date_input("Fecha de Trabajo", value=hoy)
        fecha_str = fecha_cierre.strftime("%Y-%m-%d")

        # Verificar cierre
        ws_c = sheet.worksheet(HOJA_CIERRES)
        df_c = leer_datos_seguro(ws_c)
        cierre_previo = None
        if not df_c.empty:
            df_c.columns = df_c.columns.str.strip() # LIMPIEZA DE ESPACIOS
            res = df_c[df_c["Fecha"] == fecha_str]
            if not res.empty: cierre_previo = res.iloc[0]

        if cierre_previo is not None:
            st.success(f"✅ DÍA YA CERRADO - Z-Report: {cierre_previo.get('Numero_Cierre_Loyverse', 'S/N')}")
            m1, m2, m3 = st.columns(3)
            # Usamos .get para que si no encuentra la columna por una letra, no explote
            m1.metric("Efectivo Contado", formato_moneda(cierre_previo.get('Saldo_Real_Cor', 0)))
            m2.metric("Diferencia", formato_moneda(cierre_previo.get('Diferencia', 0)))
            m3.metric("Profit Ahorrado", formato_moneda(cierre_previo.get('Profit_Retenido', 0)))
        else:
            df_tickets, ws_v = cargar_movimientos_desglosados(sheet, fecha_str)
            
            if df_tickets is None or df_tickets.empty:
                st.warning("No hay ventas registradas en esta fecha.")
            else:
                with st.expander("🛠️ Auditoría de Tickets (Pagos Mixtos)", expanded=True):
                    df_tickets["Suma_Auditada"] = df_tickets["Efectivo_Real"] + df_tickets["Nequi_Real"] + df_tickets["Tarjeta_Real"]
                    df_ed = st.data_editor(
                        df_tickets[["Hora", "Numero_Recibo", "Total_Dinero", "Efectivo_Real", "Nequi_Real", "Tarjeta_Real", "Suma_Auditada"]],
                        column_config={
                            "Total_Dinero": st.column_config.NumberColumn("Valor Ticket", format="$%d", disabled=True),
                            "Efectivo_Real": st.column_config.NumberColumn("Efectivo $", format="$%d"),
                            "Nequi_Real": st.column_config.NumberColumn("Nequi $", format="$%d"),
                            "Tarjeta_Real": st.column_config.NumberColumn("Tarjeta $", format="$%d"),
                            "Suma_Auditada": st.column_config.NumberColumn("Suma", format="$%d", disabled=True),
                        },
                        hide_index=True, use_container_width=True, key="editor_teso_final"
                    )
                    errores_suma = df_ed[abs(df_ed["Total_Dinero"] - df_ed["Suma_Auditada"]) > 1]
                    if not errores_suma.empty:
                        st.error("⚠️ El desglose no coincide con el total en algunos tickets.")

                # KPIs
                v_total = df_ed["Total_Dinero"].sum()
                v_efec = df_ed["Efectivo_Real"].sum()
                v_nequi = df_ed["Nequi_Real"].sum()
                v_tarj = df_ed["Tarjeta_Real"].sum()
                
                try:
                    ws_g = sheet.worksheet(HOJA_GASTOS)
                    df_g = leer_datos_seguro(ws_g)
                    g_efec = df_g[(df_g["Fecha"] == fecha_str) & (df_g["Metodo_Pago"].str.contains("Efectivo", na=False))]["Monto"].astype(float).sum()
                except: g_efec = 0
                
                saldo_teo = v_efec - g_efec

                st.markdown("#### 📊 Resumen Financiero Auditado")
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("VENTA TOTAL", formato_moneda(v_total))
                k2.metric("Total Efectivo", formato_moneda(v_efec))
                k3.metric("Total Nequi", formato_moneda(v_nequi))
                k4.metric("Total Tarjetas", formato_moneda(v_tarj))

                st.markdown("---")
                st.markdown("#### 💵 Arqueo de Caja")
                a1, a2, a3 = st.columns(3)
                a1.metric("(+) Entradas Efec.", formato_moneda(v_efec))
                a2.metric("(-) Gastos Caja", formato_moneda(g_efec))
                a3.metric("(=) DEBE HABER", formato_moneda(saldo_teo))

                real = st.number_input("¿Cuánto efectivo contaste?", min_value=0.0, step=500.0)
                diff = real - saldo_teo
                
                if diff == 0: st.success(f"### ✅ CORRECTO: {formato_moneda(diff)}")
                else: st.error(f"### 🔴 DIFERENCIA: {formato_moneda(diff)}")

                z_rep = st.text_input("Z-Report #")
                
                if st.button("🔒 GUARDAR CIERRE DEFINITIVO", type="primary", use_container_width=True):
                    if not errores_suma.empty: st.warning("Corrige el desglose.")
                    elif not z_rep: st.warning("Ingresa Z-Report.")
                    else:
                        datos = {
                            "Fecha": fecha_str, "Hora_Cierre": datetime.now(ZONA_HORARIA).strftime("%H:%M"),
                            "Saldo_Teorico_E": saldo_teo, "Saldo_Real_Cor": real,
                            "Diferencia": diff, "Total_Nequi": v_nequi, "Total_Tarjetas": v_tarj,
                            "Notas": "", "Profit_Retenido": v_total * 0.05,
                            "Estado_Ahorro": "Pendiente", "Numero_Cierre_Loyverse": z_rep
                        }
                        ws_c.append_row([str(datos.get(h, "")) for h in HEADERS_CIERRE])
                        st.balloons(); time.sleep(1); st.rerun()

    # --- PESTAÑA DE HISTORIAL CORREGIDA ---
    with tab_historial:
        st.subheader("📜 Historial de Cierres")
        try:
            df_h = leer_datos_seguro(sheet.worksheet(HOJA_CIERRES))
            if not df_h.empty:
                # 1. Limpiar nombres de columnas por si hay espacios en el Excel
                df_h.columns = df_h.columns.str.strip()
                
                # 2. Ordenar por fecha
                df_h = df_h.sort_values("Fecha", ascending=False).head(15)
                
                # 3. Definir qué columnas queremos mostrar (Solo las que existan)
                cols_posibles = ["Fecha", "Numero_Cierre_Loyverse", "Saldo_Teorico_E", "Saldo_Real_Cor", "Diferencia", "Profit_Retenido"]
                cols_visibles = [c for c in cols_posibles if c in df_h.columns]
                
                # 4. Formatear dinero de forma segura
                for col in cols_visibles:
                    if col != "Fecha" and col != "Numero_Cierre_Loyverse":
                        df_h[col] = pd.to_numeric(df_h[col], errors='coerce').apply(formato_moneda)
                
                st.dataframe(df_h[cols_visibles], use_container_width=True, hide_index=True)
            else:
                st.info("No hay cierres registrados.")
        except Exception as e:
            st.error(f"Error al cargar historial: {e}")
