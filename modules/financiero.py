import streamlit as st
import pandas as pd
from datetime import datetime
import calendar
import time
from utils import conectar_google_sheets, subir_foto_drive, generar_id, leer_datos_seguro, limpiar_numero, ZONA_HORARIA

# --- CONFIGURACIÓN ---
HOJA_CONFIG = "DB_CONFIG"
HOJA_PAGOS = "LOG_PAGOS_GASTOS"

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

# --- GESTIÓN DE CONFIGURACIÓN (SIN DUPLICADOS) ---

def cargar_config_gastos(sheet):
    """Lee los gastos fijos evitando duplicados en la carga."""
    try:
        ws = sheet.worksheet(HOJA_CONFIG)
        # Leemos directo sin caché para tener datos frescos
        data = ws.get_all_records()
        df_config = pd.DataFrame(data)
        
        gastos = []
        sugeridos = ["Arriendo Local", "Nómina Fija", "Servicios Públicos", "Internet", "Marketing", "Contador", "Mantenimiento"]
        encontrados = set()

        if not df_config.empty:
            # Filtrar solo parámetros de gastos fijos
            mask = df_config['Parametro'].str.startswith("GASTO_FIJO_", na=False)
            df_gastos = df_config[mask]
            
            for _, row in df_gastos.iterrows():
                param = str(row['Parametro'])
                nombre = param.replace("GASTO_FIJO_", "").replace("_", " ")
                
                valor_raw = str(row.get("Valor", "0|5|Mensual"))
                parts = valor_raw.split("|")
                
                gastos.append({
                    "Concepto": nombre,
                    "Valor Total Mensual": limpiar_numero(parts[0]),
                    "Día de Pago": int(limpiar_numero(parts[1] if len(parts) > 1 else 5)),
                    "Frecuencia": parts[2] if len(parts) > 2 else "Mensual"
                })
                encontrados.add(nombre)
        
        for s in sugeridos:
            if s not in encontrados:
                gastos.append({"Concepto": s, "Valor Total Mensual": 0.0, "Día de Pago": 5, "Frecuencia": "Mensual"})
                
        return pd.DataFrame(gastos)
    except:
        return pd.DataFrame(columns=["Concepto", "Valor Total Mensual", "Día de Pago", "Frecuencia"])

def guardar_config_gastos(sheet, df_editado):
    """Sobrescribe la configuración limpiando el caché para evitar duplicados."""
    try:
        ws = sheet.worksheet(HOJA_CONFIG)
        data_actual = ws.get_all_records()
        df_actual = pd.DataFrame(data_actual)
        
        # 1. Preservar lo que NO es gasto fijo
        if not df_actual.empty:
            df_final = df_actual[~df_actual['Parametro'].str.startswith("GASTO_FIJO_", na=False)].copy()
        else:
            df_final = pd.DataFrame(columns=["Parametro", "Valor", "Descripcion"])

        # 2. Nuevos gastos desde el editor
        nuevos_filas = []
        for _, row in df_editado.iterrows():
            concepto_limpio = str(row["Concepto"]).strip()
            if concepto_limpio:
                nuevos_filas.append({
                    "Parametro": f"GASTO_FIJO_{concepto_limpio.replace(' ', '_')}",
                    "Valor": f"{row['Valor Total Mensual']}|{int(row['Día de Pago'])}|{row['Frecuencia']}",
                    "Descripcion": f"Carga fabril: {concepto_limpio}"
                })
        
        df_nuevos = pd.DataFrame(nuevos_filas)
        df_update = pd.concat([df_final, df_nuevos], ignore_index=True)
        df_update = df_update[["Parametro", "Valor", "Descripcion"]]

        # 3. Limpiar y actualizar Google Sheets
        ws.clear()
        ws.update([df_update.columns.values.tolist()] + df_update.values.tolist())
        
        # 4. Forzar limpieza de memoria de Streamlit
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Error al guardar: {e}")
        return False

def registrar_pago_realizado(sheet, datos):
    try:
        try: ws = sheet.worksheet(HOJA_PAGOS)
        except: 
            ws = sheet.add_worksheet(title=HOJA_PAGOS, rows="1000", cols="10")
            ws.append_row(["ID_Pago", "Fecha", "Hora", "Concepto", "Monto", "Metodo", "Referencia", "URL_Soporte", "Responsable"])
        ws.append_row(datos)
        return True
    except: return False

# --- INTERFAZ PRINCIPAL ---

def show(sheet):
    st.title("💼 Departamento Financiero")
    st.caption("Configuración de Carga Fabril y Pagos.")
    st.markdown("---")
    
    if not sheet: return

    # Cargar datos frescos
    df_gastos = cargar_config_gastos(sheet)

    # Barra de Progreso
    hoy = datetime.now(ZONA_HORARIA)
    dia_actual = hoy.day
    dias_mes = calendar.monthrange(hoy.year, hoy.month)[1]
    progreso = dia_actual / dias_mes
    
    st.write(f"📅 **Estado del Mes:** Día {dia_actual} de {dias_mes}")
    st.progress(progreso)

    tab_carga, tab_agenda, tab_hist = st.tabs([
        "⚙️ CARGA FABRIL (CONFIGURAR)", 
        "📅 AGENDA & PAGOS", 
        "🗄️ HISTORIAL PAGOS"
    ])

    with tab_carga:
        st.subheader("Configuración de Obligaciones Fijas")
        
        df_editado = st.data_editor(
            df_gastos,
            num_rows="dynamic",
            column_config={
                "Concepto": st.column_config.TextColumn("Concepto", required=True),
                "Valor Total Mensual": st.column_config.NumberColumn("Monto Mensual ($)", step=1000, format="$%d"),
                "Día de Pago": st.column_config.NumberColumn("Día Límite", min_value=1, max_value=31),
                "Frecuencia": st.column_config.SelectboxColumn("Frecuencia", options=["Mensual", "Quincenal"], required=True)
            },
            use_container_width=True,
            hide_index=True,
            key="editor_financiero_v3"
        )
        
        total_fijos = df_editado["Valor Total Mensual"].sum()
        c_tot, c_btn = st.columns([2, 1])
        c_tot.metric("Presupuesto Fijo Total", formato_moneda(total_fijos))
        
        if c_btn.button("💾 GUARDAR Y LIMPIAR DUPLICADOS", type="primary", use_container_width=True):
            if guardar_config_gastos(sheet, df_editado):
                st.success("✅ Datos sincronizados correctamente.")
                time.sleep(1)
                st.rerun()

    with tab_agenda:
        st.subheader("🔔 Calendario de Obligaciones")
        
        agenda_items = []
        for _, row in df_gastos.iterrows():
            nombre = row["Concepto"]
            total = row["Valor Total Mensual"]
            dia_base = int(row["Día de Pago"])
            freq = row["Frecuencia"]
            
            if freq == "Mensual":
                agenda_items.append({"Concepto": nombre, "Monto": total, "Día": dia_base})
            elif freq == "Quincenal":
                parcial = total / 2
                agenda_items.append({"Concepto": f"{nombre} (1a Q)", "Monto": parcial, "Día": dia_base})
                dia_2 = (dia_base + 15) if (dia_base + 15) <= dias_mes else dias_mes
                agenda_items.append({"Concepto": f"{nombre} (2a Q)", "Monto": parcial, "Día": dia_2})
        
        df_agenda = pd.DataFrame(agenda_items).sort_values("Día")
        
        col_urg, col_prox, col_fut = st.columns(3)
        lista_pagar_hoy = []
        
        with col_urg:
            st.error("🚨 **VENCIDOS O HOY**")
            for _, item in df_agenda.iterrows():
                if item["Día"] <= dia_actual:
                    st.write(f"• **{item['Concepto']}**")
                    st.caption(f"💰 {formato_moneda(item['Monto'])} | Día {item['Día']}")
                    lista_pagar_hoy.append(f"{item['Concepto']} - {formato_moneda(item['Monto'])}")

        with col_prox:
            st.warning("⚠️ **PRÓXIMOS 7 DÍAS**")
            for _, item in df_agenda.iterrows():
                if dia_actual < item["Día"] <= dia_actual + 7:
                    st.write(f"• {item['Concepto']} (Día {item['Día']})")

        with col_fut:
            st.success("📆 **FUTURO**")
            for _, item in df_agenda.iterrows():
                if item["Día"] > dia_actual + 7:
                    st.write(f"• {item['Concepto']} (Día {item['Día']})")

        st.markdown("---")
        st.subheader("💸 Registrar Pago")
        
        with st.container(border=True):
            c_p1, c_p2 = st.columns(2)
            with c_p1:
                opcion_pago = st.selectbox("¿Qué vas a pagar?", ["Seleccionar..."] + lista_pagar_hoy + ["Otro"])
                monto_pagar = st.number_input("Monto Real a Pagar", min_value=0.0, step=10000.0)
            with c_p2:
                metodo = st.selectbox("Medio de Pago", ["Transferencia/Nequi", "Efectivo"])
                soporte = st.file_uploader("Recibo (PDF/Foto)", type=["jpg", "png", "jpeg", "pdf"])
            
            ref = st.text_input("Comprobante / Nota")
            
            if st.button("🚀 REGISTRAR PAGO", type="primary", use_container_width=True):
                if monto_pagar > 0 and opcion_pago != "Seleccionar...":
                    with st.status("Procesando...", expanded=True):
                        link = "Sin Soporte"
                        if soporte:
                            nombre_carpeta = opcion_pago.split(" - ")[0].upper().replace(" ", "_")
                            link = subir_foto_drive(soporte, subcarpeta=nombre_carpeta, carpeta_raiz="COSTOS_FIJOS_SOPORTES")
                        
                        id_pago = f"PAY-{generar_id()}"
                        f_hoy = datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d")
                        h_hoy = datetime.now(ZONA_HORARIA).strftime("%H:%M")
                        
                        datos_pago = [id_pago, f_hoy, h_hoy, opcion_pago, monto_pagar, metodo, ref, link, "Admin"]
                        
                        if registrar_pago_realizado(sheet, datos_pago):
                            st.success("Pago registrado."); time.sleep(1.5); st.rerun()
                else:
                    st.warning("Verifica el monto y el concepto.")

    with tab_hist:
        st.subheader("🗄️ Historial de Pagos")
        try:
            ws_h = sheet.worksheet(HOJA_PAGOS)
            df_h = leer_datos_seguro(ws_h)
            if not df_h.empty:
                df_h["Monto"] = pd.to_numeric(df_h["Monto"], errors='coerce').apply(formato_moneda)
                st.dataframe(
                    df_h[["Fecha", "Concepto", "Monto", "Metodo", "URL_Soporte"]].sort_values("Fecha", ascending=False),
                    use_container_width=True,
                    column_config={"URL_Soporte": st.column_config.LinkColumn("Ver Recibo")},
                    hide_index=True
                )
            else: st.info("No hay pagos registrados.")
        except: st.info("Base de datos de pagos nueva.")
