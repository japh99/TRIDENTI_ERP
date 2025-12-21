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
    try: 
        return f"$ {int(float(valor)):,}".replace(",", ".")
    except: 
        return "$ 0"

# --- GESTIÓN DE CONFIGURACIÓN (SIN DUPLICADOS) ---

def cargar_config_gastos(sheet):
    """Lee los gastos fijos de DB_CONFIG y los formatea para la tabla."""
    try:
        ws = sheet.worksheet(HOJA_CONFIG)
        df_config = leer_datos_seguro(ws)
        gastos = []
        
        # Conceptos sugeridos por defecto si la base está vacía
        sugeridos = ["Arriendo Local", "Nómina Fija", "Servicios Públicos", "Internet", "Marketing", "Contador", "Mantenimiento"]
        encontrados = []

        if not df_config.empty:
            for _, row in df_config.iterrows():
                param = str(row.get("Parametro", ""))
                # Filtrar solo lo que sea gasto fijo
                if param.startswith("GASTO_FIJO_"):
                    nombre = param.replace("GASTO_FIJO_", "").replace("_", " ")
                    valor_raw = str(row.get("Valor", "0|5|Mensual"))
                    
                    parts = valor_raw.split("|")
                    val = parts[0]
                    dia = parts[1] if len(parts) > 1 else "5"
                    freq = parts[2] if len(parts) > 2 else "Mensual"
                    
                    gastos.append({
                        "Concepto": nombre,
                        "Valor Total Mensual": limpiar_numero(val),
                        "Día de Pago": int(limpiar_numero(dia)),
                        "Frecuencia": freq
                    })
                    encontrados.append(nombre)
        
        # Agregar sugeridos que no estén en el Excel
        for s in sugeridos:
            if s not in encontrados:
                gastos.append({
                    "Concepto": s, 
                    "Valor Total Mensual": 0.0, 
                    "Día de Pago": 5, 
                    "Frecuencia": "Mensual"
                })
                
        return pd.DataFrame(gastos)
    except:
        return pd.DataFrame(columns=["Concepto", "Valor Total Mensual", "Día de Pago", "Frecuencia"])

def guardar_config_gastos(sheet, df_editado):
    """Guarda la configuración sobrescribiendo para evitar duplicados."""
    try:
        ws = sheet.worksheet(HOJA_CONFIG)
        df_actual = leer_datos_seguro(ws)
        
        # 1. Separar lo que NO es gasto fijo (para no borrarlo)
        if not df_actual.empty:
            df_otros = df_actual[~df_actual['Parametro'].str.startswith("GASTO_FIJO_", na=False)].copy()
        else:
            df_otros = pd.DataFrame(columns=["Parametro", "Valor", "Descripcion"])

        # 2. Convertir los datos de la tabla de la App al formato de la DB
        nuevos_registros = []
        for _, row in df_editado.iterrows():
            concepto = str(row["Concepto"]).strip()
            if concepto and concepto != "None":
                param_id = f"GASTO_FIJO_{concepto.replace(' ', '_')}"
                valor_str = f"{row['Valor Total Mensual']}|{int(row['Día de Pago'])}|{row['Frecuencia']}"
                nuevos_registros.append({
                    "Parametro": param_id,
                    "Valor": valor_str,
                    "Descripcion": f"Carga fabril: {concepto}"
                })
        
        df_nuevos_gastos = pd.DataFrame(nuevos_registros)

        # 3. Unir todo
        df_final = pd.concat([df_otros, df_nuevos_gastos], ignore_index=True)
        
        # 4. Limpiar hoja y actualizar
        ws.clear()
        ws.update([df_final.columns.values.tolist()] + df_final.values.tolist())
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

# --- INTERFAZ ---

def show(sheet):
    st.title("💼 Departamento Financiero")
    st.caption("Configuración de Carga Fabril y Agenda de Pagos.")
    st.markdown("---")
    
    if not sheet: return

    # Carga inicial
    df_gastos = cargar_config_gastos(sheet)

    # Barra de Progreso del Mes
    hoy = datetime.now(ZONA_HORARIA)
    dia_actual = hoy.day
    dias_mes = calendar.monthrange(hoy.year, hoy.month)[1]
    progreso = dia_actual / dias_mes
    
    st.write(f"📅 **Estado del Mes:** Día {dia_actual} de {dias_mes}")
    st.progress(progreso)
    st.markdown("---")

    tab_carga, tab_agenda, tab_hist = st.tabs([
        "⚙️ CARGA FABRIL (CONFIGURAR)", 
        "📅 AGENDA & PAGOS", 
        "🗄️ HISTORIAL PAGOS"
    ])

    # --- TAB 1: CONFIGURACIÓN ---
    with tab_carga:
        st.subheader("Configuración de Obligaciones Fijas")
        st.info("Define tus costos mensuales. Si borras una fila aquí, se eliminará del sistema al guardar.")
        
        df_editado = st.data_editor(
            df_gastos,
            num_rows="dynamic",
            column_config={
                "Concepto": st.column_config.TextColumn("Concepto", required=True),
                "Valor Total Mensual": st.column_config.NumberColumn("Monto Total ($)", step=1000, format="$%d"),
                "Día de Pago": st.column_config.NumberColumn("Día de Pago", min_value=1, max_value=31),
                "Frecuencia": st.column_config.SelectboxColumn("Frecuencia", options=["Mensual", "Quincenal"], required=True)
            },
            use_container_width=True,
            hide_index=True,
            key="editor_financiero_v2"
        )
        
        total_fijos = df_editado["Valor Total Mensual"].sum()
        c_tot, c_btn = st.columns([2, 1])
        c_tot.metric("Presupuesto Fijo Mensual", formato_moneda(total_fijos))
        
        if c_btn.button("💾 GUARDAR CAMBIOS", type="primary", use_container_width=True):
            if guardar_config_gastos(sheet, df_editado):
                st.success("✅ Configuración sincronizada.")
                time.sleep(1)
                st.rerun()

    # --- TAB 2: AGENDA ---
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
            st.success("📆 **RESTO DEL MES**")
            for _, item in df_agenda.iterrows():
                if item["Día"] > dia_actual + 7:
                    st.write(f"• {item['Concepto']} (Día {item['Día']})")

        st.markdown("---")
        st.subheader("💸 Registrar Pago")
        
        with st.container(border=True):
            cp1, cp2 = st.columns(2)
            with cp1:
                op_pago = st.selectbox("Obligación a pagar", ["Seleccionar..."] + lista_pagar_hoy + ["Otros"])
                monto_p = st.number_input("Monto Pagado", min_value=0.0, step=1000.0)
            with cp2:
                metodo = st.selectbox("Método", ["Transferencia", "Efectivo", "Nequi/Daviplata"])
                soporte = st.file_uploader("Evidencia (Imagen/PDF)", type=["jpg", "png", "jpeg", "pdf"])
            
            ref = st.text_input("Nota / Referencia")
            
            if st.button("🚀 REGISTRAR PAGO Y SUBIR SOPORTE", type="primary", use_container_width=True):
                if monto_p > 0 and op_pago != "Seleccionar...":
                    with st.status("Procesando pago...", expanded=True):
                        link = "Sin Soporte"
                        if soporte:
                            nombre_f = op_pago.split(" - ")[0].upper().replace(" ", "_")
                            link = subir_foto_drive(soporte, subcarpeta=nombre_f, carpeta_raiz="COSTOS_FIJOS_SOPORTES")
                        
                        id_p = f"PAY-{generar_id()}"
                        f_hoy = datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d")
                        h_hoy = datetime.now(ZONA_HORARIA).strftime("%H:%M")
                        
                        datos_p = [id_p, f_hoy, h_hoy, op_pago, monto_p, metodo, ref, link, "Admin"]
                        
                        if registrar_pago_realizado(sheet, datos_p):
                            st.success("Pago guardado.")
                            time.sleep(1.5)
                            st.rerun()
                else:
                    st.warning("Completa el monto y el concepto.")

    # --- TAB 3: HISTORIAL ---
    with tab_hist:
        st.subheader("🗄️ Historial de Egresos Fijos")
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
            else:
                st.info("No hay pagos registrados.")
        except:
            st.info("Base de datos de pagos lista para iniciar.")
