import streamlit as st
import pandas as pd
import time
from datetime import datetime
from utils import conectar_google_sheets, subir_foto_drive, generar_id, leer_datos_seguro, ZONA_HORARIA

# --- CONFIGURACIÓN ---
HOJA_GASTOS = "LOG_GASTOS"

def formato_moneda_co(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try:
        return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return str(valor)

def guardar_gasto(sheet, datos):
    try:
        try:
            ws = sheet.worksheet(HOJA_GASTOS)
        except:
            ws = sheet.add_worksheet(title=HOJA_GASTOS, rows="1000", cols="10")
            ws.append_row(["ID_Gasto", "Fecha", "Hora", "Categoria", "Descripcion", "Monto", "Metodo_Pago", "Responsable", "URL_Foto"])
        
        ws.append_rows([datos])
        return True
    except Exception as e:
        st.error(f"Error guardando: {e}")
        return False

def show(sheet):
    st.header("💸 Caja Menor & Gastos")
    st.markdown("---")
    
    if not sheet: return

    # TABS
    tab1, tab2 = st.tabs(["📝 REGISTRAR SALIDA", "📊 HISTORIAL"])

    with tab1:
        col_izq, col_der = st.columns(2)
        
        with col_izq:
            st.subheader("Datos del Gasto")
            fecha_hoy = datetime.now(ZONA_HORARIA).date()
            fecha = st.date_input("Fecha", value=fecha_hoy)
            
            # Categorías (Determinan la carpeta de la foto)
            categoria = st.selectbox("Categoría", [
                "OPERATIVO (Hielo, Gas, Aseo)",
                "MATERIA PRIMA (Urgencias)",
                "TRANSPORTE (Taxis/Domicilios)",
                "MANTENIMIENTO (Reparaciones)",
                "PERSONAL (Comida/Adelantos)",
                "ADMINISTRATIVO (Papelería)",
                "OTROS"
            ])
            
            desc = st.text_area("Descripción", placeholder="Ej: Compra de hielo por emergencia")
            
        with col_der:
            st.subheader("Pago y Evidencia")
            monto = st.number_input("Valor Pagado ($)", min_value=0, step=1000)
            metodo = st.selectbox("Método de Pago", ["Efectivo (Caja)", "Nequi Empresarial", "Bolsillo Propio (Reembolsar)"])
            responsable = st.text_input("Responsable", placeholder="¿Quién gastó?")
            
            foto = st.file_uploader("📸 Foto del Recibo", type=["jpg", "png", "jpeg"])

        st.markdown("---")
        
        if st.button("💾 REGISTRAR GASTO", type="primary", use_container_width=True):
            if monto > 0 and desc and responsable:
                with st.status("Procesando...", expanded=True) as status:
                    st.write("Subiendo evidencia...")
                    url_foto = "Sin Foto"
                    
                    if foto:
                        # Lógica de carpetas según categoría
                        carpeta = "GASTOS_VARIOS"
                        if "OPERATIVO" in categoria: carpeta = "GASTOS_OPERATIVOS"
                        elif "MATERIA" in categoria: carpeta = "GASTOS_MATERIA_PRIMA"
                        elif "TRANSPORTE" in categoria: carpeta = "GASTOS_TRANSPORTE"
                        elif "PERSONAL" in categoria: carpeta = "GASTOS_PERSONAL"
                        elif "ADMINISTRATIVO" in categoria: carpeta = "GASTOS_ADMIN"
                        
                        url_foto = subir_foto_drive(foto, subcarpeta=carpeta)
                    
                    if "Error" in url_foto:
                        status.update(label="❌ Error en foto", state="error")
                        st.error(url_foto)
                    else:
                        st.write("Guardando en base de datos...")
                        hora_actual = datetime.now(ZONA_HORARIA).strftime("%H:%M")
                        
                        nuevo_gasto = [
                            f"GST-{generar_id()}",
                            str(fecha),
                            hora_actual,
                            categoria,
                            desc,
                            monto,
                            metodo,
                            responsable,
                            url_foto
                        ]
                        
                        if guardar_gasto(sheet, nuevo_gasto):
                            status.update(label="¡Gasto Registrado!", state="complete", expanded=False)
                            st.success(f"✅ Gasto de {formato_moneda_co(monto)} guardado.")
                            time.sleep(2)
                            st.rerun()
                        else:
                            status.update(label="Error al guardar en Sheets", state="error")
            else:
                st.warning("⚠️ Por favor completa el Monto, Descripción y Responsable.")

    with tab2:
        st.subheader("📜 Últimos Movimientos")
        try:
            ws = sheet.worksheet(HOJA_GASTOS)
            df = leer_datos_seguro(ws)
            
            if not df.empty:
                # Ordenar inverso
                df = df.iloc[::-1]
                
                # Formato visual
                if "Monto" in df.columns:
                    total_gastado = pd.to_numeric(df["Monto"], errors='coerce').sum()
                    st.metric("Total Gastado (Histórico)", formato_moneda_co(total_gastado))
                    df["Monto"] = pd.to_numeric(df["Monto"], errors='coerce').apply(formato_moneda_co)

                st.dataframe(
                    df[["Fecha", "Categoria", "Descripcion", "Monto", "Responsable"]],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No hay gastos registrados.")
        except:
            st.caption("Aún no se ha creado la hoja de gastos.")