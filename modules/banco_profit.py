import streamlit as st
import pandas as pd
from datetime import datetime
import time
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero, generar_id

# --- CONFIGURACIÓN DE HOJAS ---
HOJA_CIERRES = "LOG_CIERRES_CAJA"
HOJA_RETIROS = "LOG_RETIROS_PROFIT"

# Headers según tu captura de pantalla
HEADERS_RETIROS = ["ID", "Fecha", "Hora", "Monto_Retirado", "Motivo", "Responsable"]

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

# --- FUNCIONES DE BASE DE DATOS ---

def cargar_datos(sheet):
    try:
        # 1. Cargar Cierres (Para ver el ahorro acumulado)
        ws_c = sheet.worksheet(HOJA_CIERRES)
        df_c = leer_datos_seguro(ws_c)
        
        # 2. Cargar Retiros (Tu nueva tabla)
        try:
            ws_r = sheet.worksheet(HOJA_RETIROS)
            df_r = leer_datos_seguro(ws_r)
        except:
            # Si no existe, la creamos con tus columnas
            ws_r = sheet.add_worksheet(title=HOJA_RETIROS, rows="2000", cols="10")
            ws_r.append_row(HEADERS_RETIROS)
            df_r = pd.DataFrame(columns=HEADERS_RETIROS)

        # Limpieza de datos de Cierres
        if not df_c.empty:
            df_c["Profit_Retenido"] = pd.to_numeric(df_c["Profit_Retenido"].astype(str).apply(limpiar_numero), errors='coerce').fillna(0)
            if "Estado_Ahorro" not in df_c.columns:
                df_c["Estado_Ahorro"] = "Pendiente"
        
        # Limpieza de datos de Retiros
        if not df_r.empty:
            df_r["Monto_Retirado"] = pd.to_numeric(df_r["Monto_Retirado"].astype(str).apply(limpiar_numero), errors='coerce').fillna(0)
        else:
            df_r = pd.DataFrame(columns=HEADERS_RETIROS)

        return df_c, df_r, ws_c, ws_r
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return pd.DataFrame(), pd.DataFrame(), None, None

def marcar_como_ahorrado(ws_cierres, df_cierres, fecha_cierre):
    """Actualiza la columna Estado_Ahorro en la hoja de Cierres."""
    try:
        # Buscamos la fila que coincide con la fecha
        lista_fechas = ws_cierres.col_values(1) # Asumiendo que Fecha es Col A
        if fecha_cierre in lista_fechas:
            row_idx = lista_fechas.index(fecha_cierre) + 1
            # Buscamos la columna 'Estado_Ahorro' (Col J en tu captura anterior)
            headers = ws_cierres.row_values(1)
            if "Estado_Ahorro" in headers:
                col_idx = headers.index("Estado_Ahorro") + 1
                ws_cierres.update_cell(row_idx, col_idx, "Ahorrado")
                return True
        return False
    except: return False

def registrar_retiro(ws_retiros, monto, motivo, resp):
    try:
        nueva_fila = [
            generar_id(),
            datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d"),
            datetime.now(ZONA_HORARIA).strftime("%H:%M"),
            monto,
            motivo,
            resp
        ]
        ws_retiros.append_row(nueva_fila)
        return True
    except: return False

# --- INTERFAZ ---

def show(sheet):
    st.title("🐷 Banco de Ahorro (Profit First)")
    st.caption("Gestiona tus reservas basadas en cierres de caja.")
    
    if not sheet: return

    df_c, df_r, ws_c, ws_r = cargar_datos(sheet)

    # --- LÓGICA DE SALDOS ---
    
    # 1. Ahorro Real: Suma de lo que se ha marcado como "Ahorrado" en cierres
    ahorro_total_acumulado = df_c[df_c["Estado_Ahorro"] == "Ahorrado"]["Profit_Retenido"].sum()
    
    # 2. Retiros Totales: Suma de tu tabla LOG_RETIROS_PROFIT
    retiros_totales = df_r["Monto_Retirado"].sum()
    
    # 3. Saldo Disponible
    saldo_disponible = ahorro_total_acumulado - retiros_totales

    # 4. Deuda Pendiente: Lo que está en cierres pero no se ha "Ahorrado" aún
    pendientes = df_c[df_c["Estado_Ahorro"] != "Ahorrado"].copy()
    deuda_pendiente = pendientes["Profit_Retenido"].sum()

    # --- DASHBOARD ---
    m1, m2, m3 = st.columns(3)
    m1.metric("💰 Saldo Disponible", formato_moneda(saldo_disponible), help="Ahorro Real - Retiros")
    m2.metric("⚠️ Pendiente por Guardar", formato_moneda(deuda_pendiente))
    m3.metric("💸 Total Retirado", formato_moneda(retiros_totales))

    st.markdown("---")
    t1, t2, t3 = st.tabs(["📥 INGRESAR AHORRO", "📤 REGISTRAR RETIRO", "📜 HISTORIAL"])

    with t1:
        st.subheader("Confirmar Ahorro del Día")
        if not pendientes.empty:
            # Seleccionar un cierre pendiente para "pagar" al banco
            opciones = pendientes.apply(lambda x: f"{x['Fecha']} | Sugerido: {formato_moneda(x['Profit_Retenido'])}", axis=1).tolist()
            seleccion = st.selectbox("Selecciona el cierre que vas a guardar en el banco:", opciones)
            
            if st.button("✅ Confirmar Dinero Guardado"):
                fecha_sel = seleccion.split(" | ")[0]
                if marcar_como_ahorrado(ws_c, df_c, fecha_sel):
                    st.success(f"Cierre del {fecha_sel} marcado como ahorrado."); time.sleep(1); st.rerun()
        else:
            st.success("🎉 ¡No hay ahorros pendientes!")

    with t2:
        st.subheader("Registrar Salida de Dinero")
        c1, c2 = st.columns(2)
        monto_ret = c1.number_input("Monto a retirar", min_value=0.0, step=10000.0)
        motivo_ret = c2.text_input("¿Para qué es el dinero?")
        resp_ret = st.text_input("Persona que retira")
        
        if st.button("🚨 EJECUTAR RETIRO"):
            if monto_ret > saldo_disponible:
                st.error("No hay suficiente saldo en el ahorro.")
            elif monto_ret > 0 and motivo_ret and resp_ret:
                if registrar_retiro(ws_r, monto_ret, motivo_ret, resp_ret):
                    st.success("Retiro registrado correctamente."); time.sleep(1); st.rerun()
            else:
                st.warning("Completa todos los campos.")

    with t3:
        st.subheader("Movimientos de Retiros")
        if not df_r.empty:
            df_r_view = df_r.sort_values("Fecha", ascending=False)
            # Formatear moneda para la tabla
            df_r_view["Monto_Retirado"] = df_r_view["Monto_Retirado"].apply(formato_moneda)
            st.dataframe(df_r_view[["Fecha", "Hora", "Monto_Retirado", "Motivo", "Responsable"]], use_container_width=True, hide_index=True)
        else:
            st.info("Aún no hay retiros registrados.")
