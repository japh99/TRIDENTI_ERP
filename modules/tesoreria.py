import streamlit as st
import pandas as pd
from datetime import datetime
import time
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero, generar_id

# --- CONFIGURACIÓN DE NOMBRES (Basado en tu imagen) ---
HOJA_VENTAS = "LOG_VENTAS_LOYVERSE"
HOJA_GASTOS = "LOG_PAGOS_GASTOS" # Ajustado según tu pestaña
HOJA_COMPRAS = "LOG_COMPRAS"
HOJA_CIERRES = "LOG_CIERRES_CAJA"

# Encabezados EXACTOS de tu Excel
HEADERS_CIERRE = [
    "Fecha", "Hora_Cierre", "Saldo_Teorico_E", "Saldo_Real_Con", 
    "Diferencia", "Total_Nequi", "Total_Tarjetas", "Notas", 
    "Profit_Retenido", "Estado_Ahorro", "Numero_Cierre_Loyverse"
]

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try:
        return f"$ {int(float(valor)):,}".replace(",", ".")
    except:
        return "$ 0"

# --- FUNCIONES DE DATOS ---

def asegurar_columnas(ws):
    try:
        curr = ws.row_values(1)
        if not curr: 
            ws.append_row(HEADERS_CIERRE)
    except: pass

def cargar_movimientos(sheet, fecha_str):
    try:
        # Ventas
        ws_v = sheet.worksheet(HOJA_VENTAS)
        df_v = pd.DataFrame(ws_v.get_all_records())
        if not df_v.empty:
            df_v["Fecha"] = df_v["Fecha"].astype(str)
            df_v = df_v[df_v["Fecha"] == fecha_str]
            df_v["Total_Dinero"] = pd.to_numeric(df_v["Total_Dinero"], errors='coerce').fillna(0)
        
        # Gastos
        try:
            ws_g = sheet.worksheet(HOJA_GASTOS)
            df_g = leer_datos_seguro(ws_g)
            if not df_g.empty:
                df_g["Fecha"] = df_g["Fecha"].astype(str)
                df_g = df_g[df_g["Fecha"] == fecha_str]
                df_g["Monto"] = pd.to_numeric(df_g["Monto"], errors='coerce').fillna(0)
        except: df_g = pd.DataFrame()

        return df_v, df_g, ws_v
    except Exception as e:
        st.error(f"Error cargando movimientos: {e}")
        return None, None, None

def verificar_cierre(sheet, fecha):
    try:
        ws = sheet.worksheet(HOJA_CIERRES)
        df = leer_datos_seguro(ws)
        if not df.empty and "Fecha" in df.columns:
            df["Fecha"] = df["Fecha"].astype(str)
            res = df[df["Fecha"] == fecha]
            if not res.empty: return res.iloc[0]
    except: pass
    return None

def guardar_cierre(sheet, datos_dict):
    try:
        ws = sheet.worksheet(HOJA_CIERRES)
        asegurar_columnas(ws)
        
        # Crear la fila respetando el orden de HEADERS_CIERRE
        nueva_fila = [str(datos_dict.get(h, "")) for h in HEADERS_CIERRE]
        ws.append_row(nueva_fila)
        return True
    except Exception as e:
        st.error(f"Error al guardar: {e}")
        return False

def reabrir_caja(sheet, fecha):
    try:
        ws = sheet.worksheet(HOJA_CIERRES)
        df = pd.DataFrame(ws.get_all_records())
        df["Fecha"] = df["Fecha"].astype(str)
        df_new = df[df["Fecha"] != fecha]
        ws.clear()
        ws.update([df_new.columns.values.tolist()] + df_new.values.tolist())
        return True
    except: return False

# --- INTERFAZ DE USUARIO ---
def show(sheet):
    st.title("🔐 Tesorería: Cierre de Caja")
    
    if not sheet: 
        st.error("No hay conexión con Google Sheets")
        return

    hoy = datetime.now(ZONA_HORARIA).date()
    fecha_cierre = st.date_input("Fecha de Trabajo", value=hoy)
    fecha_str = fecha_cierre.strftime("%Y-%m-%d")

    cierre_previo = verificar_cierre(sheet, fecha_str)

    if cierre_previo is not None:
        # --- MODO LECTURA (DÍA CERRADO) ---
        st.success(f"✅ DÍA CERRADO - Z-Report: {cierre_previo.get('Numero_Cierre_Loyverse', 'N/A')}")
        
        c1, c2, c3 = st.columns(3)
        real = float(limpiar_numero(cierre_previo.get("Saldo_Real_Con", 0)))
        diff = float(limpiar_numero(cierre_previo.get("Diferencia", 0)))
        prof = float(limpiar_numero(cierre_previo.get("Profit_Retenido", 0)))

        c1.metric("Efectivo en Caja", formato_moneda(real))
        c2.metric("Diferencia", formato_moneda(diff), delta=diff, delta_color="normal")
        c3.metric("Profit Ahorrado", formato_moneda(prof))

        if st.button("🗑️ REABRIR CAJA"):
            if reabrir_caja(sheet, fecha_str):
                st.success("Caja abierta")
                time.sleep(1)
                st.rerun()
    
    else:
        # --- MODO EDICIÓN (HACER EL CIERRE) ---
        df_v, df_g, ws_v = cargar_movimientos(sheet, fecha_str)
        
        if df_v is None or df_v.empty:
            st.warning("No se encontraron ventas para esta fecha.")
        else:
            # Cálculos base
            v_efec = df_v[df_v["Metodo_Pago_Real_Auditado"] == "Efectivo"]["Total_Dinero"].sum()
            v_nequi = df_v[df_v["Metodo_Pago_Real_Auditado"] == "Nequi"]["Total_Dinero"].sum()
            v_tarj = df_v[df_v["Metodo_Pago_Real_Auditado"] == "Tarjeta"]["Total_Dinero"].sum()
            v_total = df_v["Total_Dinero"].sum()
            
            g_efec = df_g[df_g["Metodo_Pago"].str.contains("Efectivo", case=False, na=False)]["Monto"].sum() if not df_g.empty else 0
            
            saldo_teo = v_efec - g_efec

            st.markdown("### 📊 Resumen del Día")
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("VENTA TOTAL", formato_moneda(v_total))
            k2.metric("Efectivo", formato_moneda(v_efec))
            k3.metric("Digital (Nequi)", formato_moneda(v_nequi))
            k4.metric("Tarjetas", formato_moneda(v_tarj))

            st.markdown("---")
            st.markdown("### 💵 Arqueo de Efectivo")
            m1, m2, m3 = st.columns(3)
            m1.metric("(+) Entradas", formato_moneda(v_efec))
            m2.metric("(-) Salidas/Gastos", formato_moneda(g_efec))
            m3.metric("(=) DEBE HABER", formato_moneda(saldo_teo))

            col_real, col_z = st.columns(2)
            real = col_real.number_input("¿Cuánto efectivo hay físicamente?", min_value=0.0, step=100.0)
            z_rep = col_z.text_input("Número de Z-Report / Cierre Loyverse")
            
            diff = real - saldo_teo
            if diff == 0: st.success("✅ Caja Cuadrada")
            else: st.error(f"🔴 DIFERENCIA: {formato_moneda(diff)}")

            pct = st.slider("% Profit Sugerido", 1, 15, 5)
            monto_prof = v_total * (pct/100)
            st.info(f"💡 Sugerencia de ahorro (Profit): {formato_moneda(monto_prof)}")

            notas = st.text_area("Notas del cierre")

            if st.button("🔒 GUARDAR CIERRE DEFINITIVO", type="primary", use_container_width=True):
                datos = {
                    "Fecha": fecha_str,
                    "Hora_Cierre": datetime.now(ZONA_HORARIA).strftime("%H:%M"),
                    "Saldo_Teorico_E": saldo_teo,
                    "Saldo_Real_Con": real,
                    "Diferencia": diff,
                    "Total_Nequi": v_nequi,
                    "Total_Tarjetas": v_tarj,
                    "Notas": notas,
                    "Profit_Retenido": monto_prof,
                    "Estado_Ahorro": "Pendiente",
                    "Numero_Cierre_Loyverse": z_rep
                }
                if guardar_cierre(sheet, datos):
                    st.balloons()
                    st.success("¡Cierre guardado exitosamente!")
                    time.sleep(2)
                    st.rerun()

    # --- HISTORIAL (ESTA ES LA PARTE QUE NO TE SALÍA) ---
    st.markdown("---")
    st.subheader("📜 Historial de Cierres")
    
    try:
        ws_h = sheet.worksheet(HOJA_CIERRES)
        df_h = leer_datos_seguro(ws_h)
        
        if not df_h.empty:
            # Ordenar por fecha
            df_h = df_h.sort_values("Fecha", ascending=False).head(15)
            
            # Formatear columnas de dinero para que se vean bien en la tabla
            cols_dinero = ["Saldo_Real_Con", "Diferencia", "Total_Nequi", "Profit_Retenido"]
            for col in cols_dinero:
                if col in df_h.columns:
                    df_h[col] = pd.to_numeric(df_h[col], errors='coerce').apply(formato_moneda)
            
            # Mostrar solo las columnas más importantes
            columnas_visibles = ["Fecha", "Numero_Cierre_Loyverse", "Saldo_Real_Con", "Diferencia", "Notas"]
            # Filtrar solo las que existen para evitar errores
            final_cols = [c for c in columnas_visibles if c in df_h.columns]
            
            st.dataframe(df_h[final_cols], use_container_width=True, hide_index=True)
        else:
            st.info("Aún no hay registros de cierres en la base de datos.")
            
    except Exception as e:
        st.warning(f"No se pudo cargar el historial. Verifica que la hoja '{HOJA_CIERRES}' tenga los encabezados correctos.")
