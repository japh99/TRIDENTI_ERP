import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import time
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero

# --- CONFIGURACIÓN ---
HOJA_VENTAS = "LOG_VENTAS_LOYVERSE"
HOJA_GASTOS = "LOG_PAGOS_GASTOS"
HOJA_CIERRES = "LOG_CIERRES_CAJA"

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

def show(sheet):
    st.title("🔐 Tesorería: Auditoría Maestra de Cierres")
    st.caption("Sincronización total con los turnos descargados de Loyverse.")

    # 1. CARGA DE DATOS (Sin filtros iniciales para no perder días)
    try:
        df_v = leer_datos_seguro(sheet.worksheet(HOJA_VENTAS))
        df_g = leer_datos_seguro(sheet.worksheet(HOJA_GASTOS))
        df_c = leer_datos_seguro(sheet.worksheet(HOJA_CIERRES))
    except:
        st.error("Error conectando con la base de datos.")
        return

    if df_v.empty:
        st.warning("No hay datos en Ventas. Escanea primero en el módulo de Ventas.")
        return

    col_id = "Shift_ID"

    tab_audit, tab_hist, tab_dash = st.tabs(["🔎 AUDITAR TURNO", "📜 HISTORIAL", "📊 DASHBOARD"])

    with tab_audit:
        # --- PROCESAMIENTO DE FECHAS ULTRA-ROBUSTO ---
        # Forzamos la conversión de fecha intentando varios formatos para que no se salte el día 20
        def corregir_fecha(f):
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
                try: return datetime.strptime(str(f).split(" ")[0], fmt).date()
                except: continue
            return None

        df_v["Fecha_Limpia"] = df_v["Fecha"].apply(corregir_fecha)
        df_v = df_v.dropna(subset=["Fecha_Limpia"]) # Quitar errores
        
        # Ordenar por fecha real (No por texto)
        df_v = df_v.sort_values("Fecha_Limpia", ascending=False)

        # Identificar qué turnos ya fueron guardados en Tesorería
        auditados = []
        if not df_c.empty and "Numero_Cierre_Loyverse" in df_c.columns:
            auditados = df_c["Numero_Cierre_Loyverse"].astype(str).str.strip().unique().tolist()
        
        # Obtener lista de turnos únicos
        df_v[col_id] = df_v[col_id].astype(str).str.strip()
        df_turnos_unicos = df_v.drop_duplicates(subset=[col_id])
        
        # Filtrar solo los que NO están en auditados
        df_pendientes = df_turnos_unicos[~df_turnos_unicos[col_id].isin(auditados)].copy()

        if df_pendientes.empty:
            st.success("🎉 ¡Todos los turnos están auditados!")
        else:
            # Selector de Mes (Para organizar como en Ventas)
            df_pendientes["Mes_Label"] = df_pendientes["Fecha_Limpia"].apply(lambda x: x.strftime('%m - %Y'))
            meses = sorted(df_pendientes["Mes_Label"].unique().tolist(), reverse=True)
            
            c_mes, c_turno = st.columns([1, 2])
            mes_sel = c_mes.selectbox("Filtrar Mes:", meses)
            
            # Turnos del mes
            df_mes = df_pendientes[df_pendientes["Mes_Label"] == mes_sel]
            df_v["Total_Dinero"] = pd.to_numeric(df_v["Total_Dinero"], errors='coerce').fillna(0)
            
            opciones_turnos = []
            ids_mapeo = []
            
            for _, row in df_mes.iterrows():
                sid = row[col_id]
                data_s = df_v[df_v[col_id] == sid]
                t_s = data_s["Total_Dinero"].sum()
                opciones_turnos.append(f"{row['Fecha_Limpia']} | Venta: {formato_moneda(t_s)} | ID: {sid[:6]}")
                ids_mapeo.append(sid)

            seleccion = c_turno.selectbox("📋 Selecciona el Cierre a auditar:", opciones_turnos)
            
            if seleccion:
                shift_id_real = ids_mapeo[opciones_turnos.index(seleccion)]
                df_sel = df_v[df_v[col_id] == shift_id_real].copy()
                fecha_turno = df_sel["Fecha_Limpia"].iloc[0]

                st.markdown(f"### 🛡️ Auditando Turno: `{shift_id_real}`")

                # --- EDITOR DE TICKETS (EDICIÓN DE VALORES POR MÉTODO) ---
                st.markdown("#### 🎫 Desglose de Pagos por Ticket")
                
                # Agrupamos por ticket para el editor
                df_tickets = df_sel.groupby("Numero_Recibo").agg({
                    "Total_Dinero": "sum",
                    "Metodo_Pag_o_Real_Auditado": "first" # Tomamos el valor que el cajero auditó en ventas
                }).reset_index()

                # Columnas para repartir la plata manualmente
                # Inicializamos con el valor total en la columna que dijo ventas
                df_tickets["Efectivo_R"] = df_tickets.apply(lambda x: x["Total_Dinero"] if x["Metodo_Pag_o_Real_Auditado"] == "Efectivo" else 0.0, axis=1)
                df_tickets["Nequi_R"] = df_tickets.apply(lambda x: x["Total_Dinero"] if x["Metodo_Pag_o_Real_Auditado"] == "Nequi" else 0.0, axis=1)
                df_tickets["Tarjeta_R"] = df_tickets.apply(lambda x: x["Total_Dinero"] if x["Metodo_Pag_o_Real_Auditado"] == "Tarjeta" else 0.0, axis=1)

                st.write("💡 *Haz doble clic en las celdas para repartir el pago si fue combinado:*")
                df_editado = st.data_editor(
                    df_tickets[["Numero_Recibo", "Total_Dinero", "Efectivo_R", "Nequi_R", "Tarjeta_R"]],
                    column_config={
                        "Numero_Recibo": st.column_config.TextColumn("Ticket #", disabled=True),
                        "Total_Dinero": st.column_config.NumberColumn("Valor Ticket", format="$%d", disabled=True),
                        "Efectivo_R": st.column_config.NumberColumn("Efectivo", min_value=0.0, format="$%d"),
                        "Nequi_R": st.column_config.NumberColumn("Nequi", min_value=0.0, format="$%d"),
                        "Tarjeta_R": st.column_config.NumberColumn("Tarjeta", min_value=0.0, format="$%d"),
                    },
                    hide_index=True, use_container_width=True, key="editor_tesoreria_tickets"
                )

                # --- RE-CÁLCULOS ---
                v_bruta = df_editado["Total_Dinero"].sum()
                v_efectivo_total = df_editado["Efectivo_R"].sum()
                v_digital_total = df_editado["Nequi_R"].sum()
                v_tarjeta_total = df_editado["Tarjeta_R"].sum()

                # Gastos de Caja (Sincronizados por fecha exacta)
                df_g["Fecha_Limpia"] = df_g["Fecha"].apply(corregir_fecha)
                gastos_turno = df_g[(df_g["Fecha_Limpia"] == fecha_turno) & (df_g["Metodo"].str.contains("Efectivo", case=False, na=False))].copy()
                total_gastos = pd.to_numeric(gastos_turno["Monto"], errors='coerce').fillna(0).sum()

                debe_haber = v_efectivo_total - total_gastos

                # Dashboard de Auditoría
                st.write("")
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("VENTA BRUTA", formato_moneda(v_bruta))
                k2.metric("EFECTIVO (Auditado)", formato_moneda(v_efectivo_total))
                k3.metric("GASTOS (Salida)", f"- {formato_moneda(total_gastos)}", delta_color="inverse")
                k4.metric("DEBE HABER CAJA", formato_moneda(debe_haber))

                st.markdown("---")
                
                # ENTRADA DE CAJA REAL
                c_real, c_z = st.columns(2)
                f_real = c_real.number_input("💵 Efectivo Físico Recibido (Contado):", min_value=0.0, step=1000.0)
                z_rep = c_z.text_input("📑 Z-Report / Ticket:", value=shift_id_real[:10])

                diff = f_real - debe_haber
                if diff == 0: st.success("### ✅ CAJA CUADRADA")
                elif diff > 0: st.info(f"### 🔵 SOBRANTE: {formato_moneda(diff)}")
                else: st.error(f"### 🔴 FALTANTE: {formato_moneda(diff)}")

                # AHORRO
                st.markdown("#### 🐷 Reserva Banco Profit")
                pct = st.slider("% Ahorro (Sobre Venta Bruta)", 1, 15, 5)
                monto_ahorro = v_bruta * (pct / 100)
                st.warning(f"Se enviará orden de ahorro por: **{formato_moneda(monto_ahorro)}**")

                if st.button("🔒 GUARDAR Y FINALIZAR AUDITORÍA", type="primary", use_container_width=True):
                    # Datos para LOG_CIERRES_CAJA
                    datos = [fecha_turno.strftime("%Y-%m-%d"), datetime.now(ZONA_HORARIA).strftime("%H:%M"), 
                             debe_haber, f_real, diff, v_digital_total, v_tarjeta_total, 
                             "Auditoría Detallada", monto_ahorro, "Pendiente", shift_id_real]
                    
                    try:
                        sheet.worksheet(HOJA_CIERRES).append_row(datos)
                        st.balloons(); st.success("Guardado."); time.sleep(1.5); st.rerun()
                    except Exception as e: st.error(f"Error: {e}")

    with tab_hist:
        st.subheader("📜 Historial de Turnos")
        if not df_c.empty:
            st.dataframe(df_c.sort_values("Fecha", ascending=False), use_container_width=True, hide_index=True)

    with tab_dash:
        st.subheader("📊 Dashboard")
        if not df_c.empty:
            df_c["Diferencia"] = pd.to_numeric(df_c["Diferencia"], errors='coerce').fillna(0)
            st.plotly_chart(px.bar(df_c, x="Fecha", y="Diferencia", color="Diferencia", title="Sobrantes/Faltantes"), use_container_width=True)
