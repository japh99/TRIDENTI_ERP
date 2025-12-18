import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import uuid
import time
from utils import conectar_google_sheets, leer_datos_seguro, generar_id, limpiar_numero, ZONA_HORARIA

# --- CONFIGURACIÓN ---
HOJA_ACTIVOS = "DB_ACTIVOS"
HOJA_MANTENIMIENTOS = "LOG_MANTENIMIENTOS"

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

def calcular_proximo_mto(ultimo_str, frecuencia_dias):
    try:
        if not ultimo_str or frecuencia_dias <= 0: return None
        ultimo = datetime.strptime(str(ultimo_str), "%Y-%m-%d").date()
        proximo = ultimo + timedelta(days=int(frecuencia_dias))
        return proximo
    except: return None

def registrar_mantenimiento_realizado(sheet, id_activo, fecha, costo, tecnico, notas, nuevo_estado):
    """Guarda el log y actualiza la fecha en el activo."""
    try:
        # 1. VERIFICAR O CREAR HOJA LOG
        try:
            ws_log = sheet.worksheet(HOJA_MANTENIMIENTOS)
        except:
            ws_log = sheet.add_worksheet(title=HOJA_MANTENIMIENTOS, rows="1000", cols="10")
            ws_log.append_row(["ID_Log", "ID_Activo", "Fecha", "Costo", "Tecnico", "Notas"])
        
        # Guardar en LOG
        log = [generar_id(), id_activo, str(fecha), costo, tecnico, notas]
        ws_log.append_row(log)
            
        # 2. ACTUALIZAR ACTIVO
        ws_act = sheet.worksheet(HOJA_ACTIVOS)
        cell = ws_act.find(id_activo)
        if cell:
            # Columna G (7) = Ultimo Mto, Columna H (8) = Estado
            ws_act.update_cell(cell.row, 7, str(fecha))
            ws_act.update_cell(cell.row, 8, nuevo_estado)
            
        return True
    except Exception as e:
        st.error(f"Error registrando servicio: {e}")
        return False

def guardar_activo(sheet, datos, modo):
    try:
        # 1. VERIFICAR O CREAR HOJA ACTIVOS
        try:
            ws = sheet.worksheet(HOJA_ACTIVOS)
        except:
            ws = sheet.add_worksheet(title=HOJA_ACTIVOS, rows="1000", cols="10")
            ws.append_row(["ID", "Nombre", "Marca", "Serie", "Ubicacion", "Frecuencia_Dias", "Ultimo_Mto", "Estado", "Fecha_Compra"])

        if modo == "Nuevo":
            ws.append_row(datos)
        else:
            cell = ws.find(datos[0]) # Busca por ID
            # Actualiza rango A:I (9 columnas)
            rango = f"A{cell.row}:I{cell.row}"
            ws.update(rango, [datos])
        return True
    except Exception as e:
        st.error(f"Error guardando activo: {e}")
        return False

def show(sheet):
    st.title("🛠️ Gestión de Activos y Mantenimiento")
    st.caption("Hoja de vida de equipos, alertas y bitácora de servicios.")
    st.markdown("---")
    
    if not sheet: return

    # Carga Segura
    try:
        ws = sheet.worksheet(HOJA_ACTIVOS)
        df = leer_datos_seguro(ws)
    except:
        df = pd.DataFrame(columns=["ID", "Nombre", "Marca", "Serie", "Ubicacion", "Frecuencia_Dias", "Ultimo_Mto", "Estado", "Fecha_Compra"])

    # Carga de Historial
    try:
        ws_log = sheet.worksheet(HOJA_MANTENIMIENTOS)
        df_log = leer_datos_seguro(ws_log)
    except:
        df_log = pd.DataFrame()

    tab_equipos, tab_alertas, tab_reg, tab_hist = st.tabs([
        "📟 MIS EQUIPOS", 
        "🚨 SEMÁFORO", 
        "📝 REGISTRAR SERVICIO", 
        "🗄️ HISTORIAL GENERAL"
    ])

    # --- TAB 1: CRUD EQUIPOS ---
    with tab_equipos:
        c_mode, c_sel = st.columns([1, 2])
        modo = c_mode.radio("Acción", ["Nuevo Equipo", "Editar"], horizontal=True, label_visibility="collapsed")
        
        # Variables
        id_act = f"EQ-{generar_id()}"
        nombre = ""
        marca = ""
        serie = ""
        ubicacion = "Cocina"
        freq = 90
        ultimo = str(datetime.now(ZONA_HORARIA).date())
        estado = "Operativo"
        compra = str(datetime.now(ZONA_HORARIA).date())
        
        if modo == "Editar" and not df.empty:
            lista_equipos = df["Nombre"].tolist()
            if lista_equipos:
                sel = c_sel.selectbox("Seleccionar Equipo:", lista_equipos)
                if sel:
                    d = df[df["Nombre"] == sel].iloc[0]
                    id_act = d["ID"]
                    nombre = d["Nombre"]
                    marca = d["Marca"]
                    serie = d["Serie"]
                    ubicacion = d["Ubicacion"]
                    freq = int(limpiar_numero(d["Frecuencia_Dias"]))
                    ultimo = d["Ultimo_Mto"]
                    estado = d["Estado"]
                    compra = d["Fecha_Compra"]

        with st.container(border=True):
            st.subheader(f"{nombre if nombre else 'Nuevo Equipo'}")
            c1, c2 = st.columns(2)
            n_nom = c1.text_input("Nombre del Equipo", value=nombre, placeholder="Ej: Nevera Vertical")
            n_marca = c2.text_input("Marca / Modelo", value=marca)
            
            c3, c4 = st.columns(2)
            n_serie = c3.text_input("Serial / Placa", value=serie)
            n_ubi = c4.selectbox("Ubicación", ["Cocina", "Barra", "Caja", "Bodega", "Salón"], index=["Cocina", "Barra", "Caja", "Bodega", "Salón"].index(ubicacion) if ubicacion in ["Cocina", "Barra", "Caja", "Bodega", "Salón"] else 0)
            
            st.markdown("---")
            st.write("🔧 **Plan de Mantenimiento**")
            c5, c6, c7 = st.columns(3)
            n_freq = c5.number_input("Frecuencia (Días)", value=freq, min_value=0, help="Cada cuánto se debe revisar. 0 = Sin mantenimiento.")
            try: d_val = datetime.strptime(ultimo, "%Y-%m-%d").date()
            except: d_val = datetime.now(ZONA_HORARIA).date()
            n_ult = c6.date_input("Último Mantenimiento", value=d_val)
            n_est = c7.selectbox("Estado Actual", ["Operativo", "Fallando", "En Reparación", "Baja"], index=["Operativo", "Fallando", "En Reparación", "Baja"].index(estado) if estado in ["Operativo", "Fallando", "En Reparación", "Baja"] else 0)
            
            try: d_comp = datetime.strptime(compra, "%Y-%m-%d").date()
            except: d_comp = datetime.now(ZONA_HORARIA).date()
            n_compra = st.date_input("Fecha de Compra (Garantía)", value=d_comp)

            if st.button("💾 GUARDAR EQUIPO", type="primary", use_container_width=True):
                if n_nom:
                    datos = [id_act, n_nom, n_marca, n_serie, n_ubi, n_freq, str(n_ult), n_est, str(n_compra)]
                    if guardar_activo(sheet, datos, "Nuevo" if modo == "Nuevo Equipo" else "Editar"):
                        st.success("Guardado.")
                        time.sleep(1); st.rerun()
                else: st.warning("Nombre obligatorio")
        
        if not df.empty:
            st.markdown("---")
            st.caption("Inventario de Activos:")
            st.dataframe(df[["Nombre", "Ubicacion", "Estado"]], use_container_width=True, hide_index=True)

    # --- TAB 2: ALERTAS ---
    with tab_alertas:
        st.subheader("🚦 Estado de Salud de Equipos")
        
        if not df.empty:
            hoy = datetime.now(ZONA_HORARIA).date()
            alertas = []
            
            for _, row in df.iterrows():
                if int(limpiar_numero(row["Frecuencia_Dias"])) > 0:
                    prox = calcular_proximo_mto(row["Ultimo_Mto"], int(limpiar_numero(row["Frecuencia_Dias"])))
                    if prox:
                        dias_restantes = (prox - hoy).days
                        estado_semaforo = "🟢 OK"
                        if dias_restantes < 0: estado_semaforo = "🔴 VENCIDO"
                        elif dias_restantes <= 7: estado_semaforo = "🟡 PRÓXIMO"
                        
                        alertas.append({
                            "Estado": estado_semaforo,
                            "Equipo": row["Nombre"],
                            "Último": row["Ultimo_Mto"],
                            "Límite": prox,
                            "Días Restantes": dias_restantes
                        })
            
            if alertas:
                df_a = pd.DataFrame(alertas).sort_values("Días Restantes")
                def color_alert(val):
                    color = 'green'
                    if 'VENCIDO' in str(val): color = 'red'
                    elif 'PRÓXIMO' in str(val): color = 'orange'
                    return f'color: {color}; font-weight: bold'
                st.dataframe(df_a.style.map(color_alert, subset=['Estado']), use_container_width=True, hide_index=True)
            else: st.info("Todo al día o sin mantenimientos programados.")
        else: st.info("Registra equipos primero.")

    # --- TAB 3: REGISTRO ---
    with tab_reg:
        st.subheader("📝 Registrar Servicio Realizado")
        
        if not df.empty:
            lista_eq = df["Nombre"].tolist()
            eq_sel = st.selectbox("¿A qué equipo se le hizo mantenimiento?", lista_eq)
            
            if eq_sel:
                row_eq = df[df["Nombre"] == eq_sel].iloc[0]
                
                # --- AQUÍ ESTÁ LA MEJORA: HISTORIAL ESPECÍFICO ---
                if not df_log.empty:
                    hist_equipo = df_log[df_log["ID_Activo"] == row_eq["ID"]]
                    if not hist_equipo.empty:
                        with st.expander(f"📜 Ver Historial de {eq_sel}", expanded=False):
                            hist_equipo["Costo"] = pd.to_numeric(hist_equipo["Costo"], errors='coerce').fillna(0)
                            gasto_total_eq = hist_equipo["Costo"].sum()
                            st.write(f"**Gasto Total Acumulado:** {formato_moneda(gasto_total_eq)}")
                            
                            hist_equipo["Costo_Vis"] = hist_equipo["Costo"].apply(formato_moneda)
                            st.dataframe(hist_equipo[["Fecha", "Tecnico", "Notas", "Costo_Vis"]], use_container_width=True, hide_index=True)

                c_m1, c_m2 = st.columns(2)
                fecha_mto = c_m1.date_input("Fecha del Servicio", value=datetime.now(ZONA_HORARIA).date())
                costo_mto = c_m2.number_input("Costo ($)", min_value=0, step=10000)
                
                tecnico = st.text_input("Técnico / Empresa")
                notas = st.text_area("Detalle del trabajo realizado")
                nuevo_est = st.selectbox("Nuevo Estado del Equipo", ["Operativo", "Fallando"], index=0)
                
                if st.button("✅ REGISTRAR Y REPROGRAMAR", type="primary"):
                    if registrar_mantenimiento_realizado(sheet, row_eq["ID"], fecha_mto, costo_mto, tecnico, notas, nuevo_est):
                        st.balloons()
                        st.success(f"Mantenimiento registrado. La fecha de 'Último Mto' de {eq_sel} ha sido actualizada.")
                        time.sleep(2); st.rerun()
        else: st.warning("Sin equipos.")

    # --- TAB 4: HISTORIAL GLOBAL (NUEVO) ---
    with tab_hist:
        st.subheader("🗄️ Bitácora General de Mantenimientos")
        if not df_log.empty:
            # Cruzar ID con Nombre para mostrar "Nevera" en vez de "EQ-A123"
            if not df.empty:
                mapa_nombres = dict(zip(df["ID"], df["Nombre"]))
                df_log["Equipo"] = df_log["ID_Activo"].map(mapa_nombres).fillna("Desconocido")
            else:
                df_log["Equipo"] = df_log["ID_Activo"]

            # Formato
            df_log["Costo"] = pd.to_numeric(df_log["Costo"], errors='coerce').fillna(0)
            total_gastado_mtos = df_log["Costo"].sum()
            st.metric("Gasto Total en Mantenimientos", formato_moneda(total_gastado_mtos))
            
            df_log["Costo"] = df_log["Costo"].apply(formato_moneda)
            
            st.dataframe(
                df_log[["Fecha", "Equipo", "Tecnico", "Notas", "Costo"]].sort_values("Fecha", ascending=False),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No hay mantenimientos registrados en la bitácora.")