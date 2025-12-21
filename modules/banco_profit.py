import streamlit as st
import pandas as pd
from datetime import datetime
import time
import uuid
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero, generar_id

# --- CONFIGURACIÓN ---
HOJA_CIERRES = "LOG_CIERRES_CAJA"
HOJA_BANCO = "LOG_BANCO_PROFIT"

# Estructura del Banco
HEADERS_BANCO = [
    "ID_Movimiento", "Fecha_Registro", "Hora", "Tipo_Movimiento", 
    "Monto", "Fecha_Referencia", "Responsable", "Notas"
]
# Fecha_Referencia = La fecha del cierre que se está pagando (ej: 2025-12-18)

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

# --- BACKEND ---

def obtener_o_crear_hoja(sheet, nombre, headers):
    try: return sheet.worksheet(nombre)
    except:
        ws = sheet.add_worksheet(title=nombre, rows="2000", cols="10")
        ws.append_row(headers)
        return ws

def cargar_datos_banco(sheet):
    """Carga los cierres (deuda potencial) y los movimientos bancarios (realidad)."""
    try:
        # 1. Cierres de Caja (Para saber qué debemos)
        ws_c = sheet.worksheet(HOJA_CIERRES)
        df_cierres = leer_datos_seguro(ws_c)
        
        # 2. Movimientos del Banco (Para saber qué tenemos)
        ws_b = obtener_o_crear_hoja(sheet, HOJA_BANCO, HEADERS_BANCO)
        df_banco = leer_datos_seguro(ws_b)

        # Limpieza de números
        if not df_cierres.empty:
            if "Profit_Sugerido" in df_cierres.columns: # Si usas la versión nueva
                col_profit = "Profit_Sugerido"
            elif "Profit_Retenido" in df_cierres.columns: # Si usas versiones mixtas
                col_profit = "Profit_Retenido"
            else:
                col_profit = None
            
            if col_profit:
                df_cierres["Monto_Profit"] = df_cierres[col_profit].astype(str).apply(limpiar_numero)
            else:
                df_cierres["Monto_Profit"] = 0.0
                
        else:
            df_cierres = pd.DataFrame(columns=["Fecha", "Monto_Profit"])

        if not df_banco.empty:
            df_banco["Monto"] = df_banco["Monto"].astype(str).apply(limpiar_numero)
        else:
            df_banco = pd.DataFrame(columns=HEADERS_BANCO)

        return df_cierres, df_banco, ws_b

    except Exception as e:
        # st.error(f"Error cargando banco: {e}") 
        return pd.DataFrame(), pd.DataFrame(), None

def registrar_movimiento(ws, tipo, monto, fecha_ref, resp, notas):
    try:
        fecha_reg = datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d")
        hora = datetime.now(ZONA_HORARIA).strftime("%H:%M")
        
        # ID, FechaReg, Hora, Tipo, Monto, FechaRef, Resp, Notas
        row = [
            generar_id(), fecha_reg, hora, tipo, 
            monto, str(fecha_ref), resp, notas
        ]
        ws.append_row(row)
        return True
    except: return False

# --- INTERFAZ ---

def show(sheet):
    st.title("🐷 Banco de Ahorro (Profit First)")
    st.caption("Administra tus utilidades y reservas.")
    st.markdown("---")
    
    if not sheet: return

    df_cierres, df_banco, ws_banco = cargar_datos_banco(sheet)

    # --- 1. CÁLCULO DE SALDOS ---
    
    # Saldo Real en Banco
    total_entradas = df_banco[df_banco["Tipo_Movimiento"] == "ENTRADA"]["Monto"].sum()
    total_salidas = df_banco[df_banco["Tipo_Movimiento"] == "SALIDA"]["Monto"].sum()
    saldo_disponible = total_entradas - total_salidas

    # Cálculo de Deuda (Pendientes)
    # Buscamos qué fechas de cierre YA tienen una entrada en el banco
    fechas_pagadas = []
    if not df_banco.empty:
        fechas_pagadas = df_banco[df_banco["Tipo_Movimiento"] == "ENTRADA"]["Fecha_Referencia"].unique().tolist()
    
    # Filtramos los cierres que NO están en la lista de pagados y tienen monto > 0
    pendientes = pd.DataFrame()
    if not df_cierres.empty:
        # Convertir a string para comparar
        df_cierres["Fecha"] = df_cierres["Fecha"].astype(str)
        # Lógica: Fecha no está en pagadas Y el monto es mayor a 0
        pendientes = df_cierres[
            (~df_cierres["Fecha"].isin(fechas_pagadas)) & 
            (df_cierres["Monto_Profit"] > 0)
        ].copy()

    total_deuda = pendientes["Monto_Profit"].sum() if not pendientes.empty else 0

    # --- DASHBOARD ---
    k1, k2, k3 = st.columns(3)
    k1.metric("💰 Saldo Disponible", formato_moneda(saldo_disponible), help="Dinero real guardado.")
    k2.metric("📥 Ahorro Total", formato_moneda(total_entradas))
    k3.metric("⚠️ Deuda Pendiente", formato_moneda(total_deuda), delta_color="inverse")

    st.markdown("---")

    tab_ingreso, tab_retiro, tab_hist = st.tabs(["🟠 INGRESAR DINERO", "💸 RETIRAR DINERO", "📜 EXTRACTO"])

    # --- TAB 1: INGRESAR (PAGAR DEUDAS) ---
    with tab_ingreso:
        st.subheader("Registrar Ahorro")
        
        if not pendientes.empty:
            st.info(f"Tienes **{len(pendientes)} días** sin transferir el ahorro.")
            
            # Crear lista bonita para el selectbox
            # Formato: "2025-12-18 | Sugerido: $ 50.000"
            opciones = pendientes.apply(
                lambda x: f"{x['Fecha']} | Sugerido: {formato_moneda(x['Monto_Profit'])}", 
                axis=1
            ).tolist()
            
            seleccion = st.selectbox("Selecciona el día que vas a pagar:", opciones)
            
            # Recuperar datos de la selección
            if seleccion:
                fecha_sel = seleccion.split(" | ")[0]
                monto_sugerido = pendientes[pendientes["Fecha"] == fecha_sel].iloc[0]["Monto_Profit"]
                
                c1, c2 = st.columns(2)
                monto_real = c1.number_input("Monto a Transferir", value=float(monto_sugerido), step=5000.0)
                nota_ingreso = c2.text_input("Nota (Opcional)", placeholder="Ej: Transferencia Nequi")
                
                if st.button("✅ CONFIRMAR INGRESO", type="primary"):
                    if registrar_movimiento(ws_banco, "ENTRADA", monto_real, fecha_sel, "Admin", nota_ingreso):
                        st.balloons()
                        st.success("¡Dinero en el banco!")
                        time.sleep(1)
                        st.rerun()
        else:
            st.success("🎉 ¡Estás al día! No debes nada al fondo.")
            
            # Opción de Aporte Voluntario
            if st.checkbox("Hacer un Aporte Extra Voluntario"):
                ce1, ce2 = st.columns(2)
                m_extra = ce1.number_input("Monto Extra", step=10000.0)
                n_extra = ce2.text_input("Motivo", value="Aporte Extra")
                if st.button("Guardar Extra"):
                    if registrar_movimiento(ws_banco, "ENTRADA", m_extra, datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d"), "Admin", n_extra):
                        st.success("Guardado."); time.sleep(1); st.rerun()

    # --- TAB 2: RETIROS ---
    with tab_retiro:
        st.subheader("Retirar Fondos")
        
        c_r1, c_r2 = st.columns(2)
        monto_ret = c_r1.number_input("Monto a Retirar", min_value=0.0, step=50000.0)
        motivo = c_r2.text_input("Motivo del Retiro", placeholder="Ej: Compra de Activo")
        responsable = st.text_input("Responsable")
        
        if st.button("🚨 REGISTRAR RETIRO", type="primary"):
            if 0 < monto_ret <= saldo_disponible:
                if motivo and responsable:
                    if registrar_movimiento(ws_banco, "SALIDA", monto_ret, datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d"), responsable, motivo):
                        st.success("Retiro exitoso."); time.sleep(1); st.rerun()
                else:
                    st.warning("Escribe motivo y responsable.")
            else:
                st.error(f"Fondos insuficientes. Máximo: {formato_moneda(saldo_disponible)}")

    # --- TAB 3: EXTRACTO ---
    with tab_hist:
        st.subheader("Movimientos")
        if not df_banco.empty:
            df_show = df_banco.sort_values("ID_Movimiento", ascending=False).copy()
            df_show["Monto"] = df_show["Monto"].apply(formato_moneda)
            
            # Colorear tipo
            def color_tipo(val):
                return 'color: green; font-weight: bold' if val == "ENTRADA" else 'color: red; font-weight: bold'

            st.dataframe(
                df_show[["Fecha_Registro", "Tipo_Movimiento", "Monto", "Fecha_Referencia", "Notas", "Responsable"]]
                .style.applymap(color_tipo, subset=["Tipo_Movimiento"]),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Sin movimientos.")
