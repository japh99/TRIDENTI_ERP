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

# --- GESTIÓN DE CONFIGURACIÓN ---
def cargar_config_gastos(sheet):
    """Lee los gastos fijos para configurar la agenda."""
    try:
        ws = sheet.worksheet(HOJA_CONFIG)
        data = ws.get_all_records()
        gastos = []
        
        sugeridos = ["Arriendo Local", "Nómina Fija", "Servicios Públicos", "Internet", "Marketing", "Contador", "Mantenimiento"]
        encontrados = []

        for row in data:
            param = str(row.get("Parametro", ""))
            if param.startswith("GASTO_FIJO_"):
                nombre = param.replace("GASTO_FIJO_", "").replace("_", " ")
                valor_raw = str(row.get("Valor", "0"))
                
                parts = valor_raw.split("|")
                val = parts[0]
                dia = parts[1] if len(parts) > 1 else "1"
                freq = parts[2] if len(parts) > 2 else "Mensual"
                
                gastos.append({
                    "Concepto": nombre,
                    "Valor Total Mensual": limpiar_numero(val),
                    "Día de Pago": int(limpiar_numero(dia)),
                    "Frecuencia": freq
                })
                encontrados.append(nombre)
        
        for s in sugeridos:
            if s not in encontrados:
                gastos.append({"Concepto": s, "Valor Total Mensual": 0.0, "Día de Pago": 5, "Frecuencia": "Mensual"})
                
        return pd.DataFrame(gastos)
    except:
        return pd.DataFrame(columns=["Concepto", "Valor Total Mensual", "Día de Pago", "Frecuencia"])

def guardar_config_gastos(sheet, df):
    try:
        ws = sheet.worksheet(HOJA_CONFIG)
        for _, row in df.iterrows():
            p = f"GASTO_FIJO_{row['Concepto'].replace(' ', '_')}"
            v = f"{row['Valor Total Mensual']}|{int(row['Día de Pago'])}|{row['Frecuencia']}"
            
            cell = ws.find(p)
            if cell: ws.update_cell(cell.row, 2, v)
            else: ws.append_row([p, v])
        return True
    except: return False

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
    st.caption("Configuración de Carga Fabril y Pagos.")
    st.markdown("---")
    
    if not sheet: return

    # Cargar Configuración
    df_gastos = cargar_config_gastos(sheet)

    # Barra de Progreso Mes
    hoy = datetime.now(ZONA_HORARIA)
    dia_actual = hoy.day
    dias_mes = calendar.monthrange(hoy.year, hoy.month)[1]
    progreso = dia_actual / dias_mes
    
    st.write(f"📅 **Progreso del Mes:** Día {dia_actual} de {dias_mes}")
    st.progress(progreso)
    st.markdown("---")

    tab_carga, tab_agenda, tab_hist = st.tabs([
        "⚙️ CARGA FABRIL (CONFIGURAR)", 
        "📅 AGENDA & PAGOS", 
        "🗄️ HISTORIAL PAGOS"
    ])

    # --- TAB 1: CONFIGURACIÓN GASTOS ---
    with tab_carga:
        st.subheader("Configuración de Obligaciones Fijas")
        st.info("Define aquí tus costos fijos mensuales y cuándo se pagan.")
        
        df_editado = st.data_editor(
            df_gastos,
            num_rows="dynamic",
            column_config={
                "Concepto": st.column_config.TextColumn("Concepto", required=True),
                "Valor Total Mensual": st.column_config.NumberColumn("Valor MENSUAL ($)", step=50000, format="$%d"),
                "Día de Pago": st.column_config.NumberColumn("Día Límite", min_value=1, max_value=31),
                "Frecuencia": st.column_config.SelectboxColumn("Frecuencia", options=["Mensual", "Quincenal"], required=True)
            },
            use_container_width=True,
            hide_index=True,
            key="editor_financiero"
        )
        
        total_fijos = df_editado["Valor Total Mensual"].sum()
        c_tot, c_btn = st.columns([2, 1])
        c_tot.metric("Total Gastos Fijos (Mes)", formato_moneda(total_fijos))
        
        if c_btn.button("💾 GUARDAR CONFIGURACIÓN", type="primary"):
            if guardar_config_gastos(sheet, df_editado):
                st.success("✅ Datos actualizados.")
                time.sleep(1); st.rerun()

    # --- TAB 2: AGENDA Y PAGOS ---
    with tab_agenda:
        st.subheader("🔔 Calendario de Obligaciones")
        
        agenda_items = []
        for _, row in df_gastos.iterrows():
            nombre = row["Concepto"]
            total = row["Valor Total Mensual"]
            dia_base = int(row["Día de Pago"])
            freq = row["Frecuencia"]
            
            # LÓGICA DE NÓMINA (QUINCENAL)
            if freq == "Mensual":
                agenda_items.append({"Concepto": nombre, "Monto": total, "Día": dia_base})
            elif freq == "Quincenal":
                parcial = total / 2
                agenda_items.append({"Concepto": f"{nombre} (1a Quincena)", "Monto": parcial, "Día": dia_base})
                # Segunda quincena 15 días después (o fin de mes)
                dia_2 = (dia_base + 15) if (dia_base + 15) <= dias_mes else dias_mes
                agenda_items.append({"Concepto": f"{nombre} (2a Quincena)", "Monto": parcial, "Día": dia_2})
        
        df_agenda = pd.DataFrame(agenda_items).sort_values("Día")
        
        col_urg, col_prox, col_fut = st.columns(3)
        lista_pagar_hoy = []
        
        with col_urg:
            st.error("🚨 **URGENTE (Hoy o Vencido)**")
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
                    st.write(f"• {item['Concepto']}")

        st.markdown("---")
        st.subheader("💸 Registrar Pago Realizado")
        
        with st.container(border=True):
            c_p1, c_p2 = st.columns(2)
            
            with c_p1:
                opcion_pago = st.selectbox("¿Qué vas a pagar?", ["Seleccionar..."] + lista_pagar_hoy + ["Otro Gasto Fijo"])
                monto_pagar = st.number_input("Monto Real a Pagar", min_value=0.0, step=10000.0)
                metodo = st.selectbox("Medio de Pago", ["Transferencia/Nequi", "Efectivo"])
                
            with c_p2:
                ref = st.text_input("Referencia / Comprobante")
                soporte = st.file_uploader("📎 Subir Recibo (PDF/Foto)", type=["jpg", "png", "jpeg", "pdf"])
            
            if st.button("✅ REGISTRAR PAGO Y SUBIR EVIDENCIA", type="primary", use_container_width=True):
                if monto_pagar > 0:
                    with st.status("Subiendo soporte a la nube...", expanded=True):
                        link = "Sin Soporte"
                        if soporte:
                            # --- NUEVA LÓGICA DE CARPETAS ---
                            # Nombre carpeta limpio (sin paréntesis extraños)
                            nombre_carpeta = opcion_pago.split(" - ")[0].split(" (")[0].upper().replace(" ", "_").replace("Ó","O").replace("Í","I")
                            
                            # USAMOS LA CARPETA RAÍZ 'COSTOS_FIJOS_SOPORTES'
                            link = subir_foto_drive(soporte, subcarpeta=nombre_carpeta, carpeta_raiz="COSTOS_FIJOS_SOPORTES")
                        
                        id_pago = f"PAY-{generar_id()}"
                        fecha_hoy = datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d")
                        hora_hoy = datetime.now(ZONA_HORARIA).strftime("%H:%M")
                        
                        datos_pago = [id_pago, fecha_hoy, hora_hoy, opcion_pago, monto_pagar, metodo, ref, link, "Admin"]
                        
                        if registrar_pago_realizado(sheet, datos_pago):
                            st.success("Pago registrado correctamente.")
                            time.sleep(2); st.rerun()
                        else:
                            st.error("Error al guardar.")
                else:
                    st.warning("Ingresa un monto válido.")

    # --- TAB 3: HISTORIAL ---
    with tab_hist:
        st.subheader("🗄️ Historial de Pagos")
        try:
            ws_h = sheet.worksheet(HOJA_PAGOS)
            df_h = leer_datos_seguro(ws_h)
            if not df_h.empty:
                df_h["Monto"] = pd.to_numeric(df_h["Monto"]).apply(formato_moneda)
                st.dataframe(
                    df_h[["Fecha", "Concepto", "Monto", "Metodo", "Referencia", "URL_Soporte"]].sort_values("Fecha", ascending=False),
                    use_container_width=True,
                    column_config={"URL_Soporte": st.column_config.LinkColumn("Ver Recibo")},
                    hide_index=True
                )
            else: st.info("No hay pagos registrados aún.")
        except: st.info("Base de datos de pagos nueva.")