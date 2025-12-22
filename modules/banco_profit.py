import streamlit as st
import pandas as pd
from datetime import datetime
import time
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero, generar_id

# --- CONFIGURACIÓN ---
HOJA_CIERRES = "LOG_CIERRES_CAJA"
HOJA_BANCO = "LOG_BANCO_MOVIMIENTOS"

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

# --- BACKEND ---

def cargar_datos_banco(sheet):
    """Carga cierres pendientes y el historial de movimientos del banco."""
    try:
        # 1. Cargar Cierres para ver qué falta por ahorrar
        ws_c = sheet.worksheet(HOJA_CIERRES)
        df_c = leer_datos_seguro(ws_c)
        
        # 2. Cargar Movimientos del Banco
        try:
            ws_b = sheet.worksheet(HOJA_BANCO)
            df_b = leer_datos_seguro(ws_b)
        except:
            # Crear la hoja de movimientos si no existe
            ws_b = sheet.add_worksheet(title=HOJA_BANCO, rows="2000", cols="10")
            headers = ["ID", "Fecha", "Hora", "Tipo", "Monto", "Referencia_Turno", "Motivo", "Responsable"]
            ws_b.append_row(headers)
            df_b = pd.DataFrame(columns=headers)

        # Limpiar datos de cierres
        if not df_c.empty:
            df_c.columns = df_c.columns.str.strip()
            df_c["Profit_Retenido"] = pd.to_numeric(df_c["Profit_Retenido"], errors='coerce').fillna(0)
            if "Estado_Ahorro" not in df_c.columns: df_c["Estado_Ahorro"] = "Pendiente"
        
        # Limpiar datos de banco
        if not df_b.empty:
            df_b["Monto"] = pd.to_numeric(df_b["Monto"], errors='coerce').fillna(0)
        else:
            df_b = pd.DataFrame(columns=["ID", "Fecha", "Hora", "Tipo", "Monto", "Referencia_Turno", "Motivo", "Responsable"])

        return df_c, df_b, ws_c, ws_b
    except Exception as e:
        st.error(f"Error cargando banco: {e}")
        return pd.DataFrame(), pd.DataFrame(), None, None

def registrar_movimiento_banco(ws_b, tipo, monto, ref, motivo, resp):
    """Registra una entrada o salida en el historial del banco."""
    try:
        fila = [
            generar_id(),
            datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d"),
            datetime.now(ZONA_HORARIA).strftime("%H:%M"),
            tipo, # ENTRADA / SALIDA
            monto,
            ref,
            motivo,
            resp
        ]
        ws_b.append_row(fila)
        return True
    except: return False

def actualizar_estado_ahorro(ws_c, shift_id_o_fecha):
    """Marca el cierre como 'Ahorrado' en la hoja de Tesorería."""
    try:
        # Buscamos por Shift_ID o por Fecha en la Columna A o L
        data = ws_c.get_all_values()
        headers = data[0]
        col_shift = headers.index("Shift_ID") + 1 if "Shift_ID" in headers else 1
        col_estado = headers.index("Estado_Ahorro") + 1
        
        for i, row in enumerate(data):
            if row[col_shift - 1] == str(shift_id_o_fecha):
                ws_c.update_cell(i + 1, col_estado, "Ahorrado")
                break
    except: pass

# --- INTERFAZ ---

def show(sheet):
    st.title("🐷 Banco Profit (Ahorro Real)")
    st.caption("Gestiona el dinero físico reservado de tus ventas.")
    
    if not sheet: return

    df_c, df_b, ws_c, ws_b = cargar_datos_banco(sheet)

    # --- 1. CÁLCULO DE SALDOS ---
    entradas = df_b[df_b["Tipo"] == "ENTRADA"]["Monto"].sum()
    salidas = df_b[df_b["Tipo"] == "SALIDA"]["Monto"].sum()
    saldo_disponible = entradas - salidas

    # Cierres que aún no se han guardado en el banco
    pendientes = df_c[df_c["Estado_Ahorro"] != "Ahorrado"].copy() if not df_c.empty else pd.DataFrame()
    ahorro_pendiente_total = pendientes["Profit_Retenido"].sum()

    # DASHBOARD
    c1, c2, c3 = st.columns(3)
    c1.metric("💰 Saldo Real en Banco", formato_moneda(saldo_disponible))
    c2.metric("⚠️ Pendiente por Guardar", formato_moneda(ahorro_pendiente_total))
    c3.metric("📤 Total Retirado", formato_moneda(salidas))

    st.markdown("---")
    t1, t2, t3 = st.tabs(["📥 CONFIRMAR AHORRO", "💸 RETIRAR DINERO", "📜 HISTORIAL COMPLETO"])

    with t1:
        st.subheader("Confirmar ingreso de ahorro")
        if not pendientes.empty:
            st.info("Selecciona un cierre de tesorería para registrar el dinero que vas a guardar físicamente.")
            
            # Etiqueta para el selector
            pendientes["Label"] = pendientes.apply(
                lambda x: f"Jornada: {x['Fecha_Cierre']} | Sugerido: {formato_moneda(x['Profit_Retenido'])}", axis=1
            )
            
            opcion = st.selectbox("Cierre pendiente:", pendientes["Label"].tolist())
            datos_sel = pendientes[pendientes["Label"] == opcion].iloc[0]
            
            # --- FLEXIBILIDAD: EDITAR EL MONTO ---
            col_ing1, col_ing2 = st.columns(2)
            monto_real = col_ing1.number_input("Monto real a guardar:", value=float(datos_sel["Profit_Retenido"]), step=1000.0)
            responsable = col_ing2.text_input("Quién guarda el dinero:", value="Admin")
            
            nota = st.text_input("Nota adicional:", placeholder="Ej: Guardado en caja fuerte de seguridad")

            if st.button("✅ CONFIRMAR Y GUARDAR DINERO", type="primary", use_container_width=True):
                if monto_real >= 0:
                    ref_turno = datos_sel.get("Shift_ID", datos_sel["Fecha_Cierre"])
                    if registrar_movimiento_banco(ws_b, "ENTRADA", monto_real, ref_turno, nota, responsable):
                        # Marcar en tesorería que este turno ya se ahorró
                        actualizar_estado_ahorro(ws_c, ref_turno)
                        st.success(f"¡Dinero guardado! Se han sumado {formato_moneda(monto_real)} al banco.")
                        st.balloons()
                        time.sleep(1); st.rerun()
        else:
            st.success("🎉 ¡Felicidades! No tienes ahorros pendientes por guardar.")

    with t2:
        st.subheader("Registrar Salida de Fondos")
        st.warning("Usa esta sección para reportar gastos pagados con el ahorro o retiros de utilidad.")
        
        col_ret1, col_ret2 = st.columns(2)
        monto_ret = col_ret1.number_input("Monto a retirar:", min_value=0.0, step=10000.0)
        motivo_ret = col_ret2.text_input("¿En qué se usará el dinero?")
        resp_ret = st.text_input("Autorizado por:")

        if st.button("🚨 EJECUTAR RETIRO", type="primary", use_container_width=True):
            if monto_ret > saldo_disponible:
                st.error("No puedes retirar más de lo que hay en el saldo disponible.")
            elif monto_ret > 0 and motivo_ret and resp_ret:
                if registrar_movimiento_banco(ws_b, "SALIDA", monto_ret, "Retiro Manual", motivo_ret, resp_ret):
                    st.success("Retiro registrado correctamente.")
                    time.sleep(1); st.rerun()
            else:
                st.warning("Completa todos los campos.")

    with t3:
        st.subheader("Movimientos de la Cuenta de Ahorros")
        if not df_b.empty:
            # Estilo para la tabla
            def color_tipo(val):
                return 'color: green; font-weight: bold' if val == "ENTRADA" else 'color: red; font-weight: bold'

            df_ver = df_b.sort_values(["Fecha", "Hora"], ascending=False).copy()
            df_ver["Monto"] = df_ver["Monto"].apply(formato_moneda)
            
            st.dataframe(
                df_ver[["Fecha", "Tipo", "Monto", "Referencia_Turno", "Motivo", "Responsable"]]
                .style.applymap(color_tipo, subset=["Tipo"]),
                use_container_width=True,
                hide_index=True
            )
            
            if st.button("🔄 ACTUALIZAR HISTORIAL"):
                st.cache_data.clear(); st.rerun()
        else:
            st.info("Aún no hay movimientos registrados en el banco.")
