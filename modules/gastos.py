import streamlit as st
import pandas as pd
import time
import os
from datetime import datetime
from utils import conectar_google_sheets, subir_foto_drive, generar_id, leer_datos_seguro, ZONA_HORARIA

# --- CONFIGURACIÓN ---
HOJA_GASTOS = "LOG_GASTOS"

def formato_moneda_co(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return str(valor)

def guardar_gasto(sheet, datos):
    try:
        try: 
            ws = sheet.worksheet(HOJA_GASTOS)
        except:
            ws = sheet.add_worksheet(title=HOJA_GASTOS, rows="2000", cols="10")
            ws.append_row(["ID_Gasto", "Fecha", "Hora", "Categoria", "Descripcion", "Monto", "Metodo_Pago", "Responsable", "URL_Foto"])
        
        # Guardado limpio en Google Sheets
        ws.append_row(datos, value_input_option='USER_ENTERED')
        return True
    except Exception as e:
        st.error(f"Error en Google Sheets: {e}")
        return False

def show(sheet):
    st.title("💸 Gastos Variables & Caja Menor")
    st.caption("Registro de salidas operativas con respaldo en la nube.")
    st.markdown("---")
    
    if not sheet: return

    # --- DIAGNÓSTICO DE SEGURIDAD (Solo visible para ti si hay error) ---
    if not os.environ.get("CLOUDINARY_API_KEY"):
        st.warning("⚠️ Advertencia: No se detectaron las llaves de Cloudinary en el sistema. Las fotos podrían fallar.")

    tab1, tab2 = st.tabs(["📝 REGISTRAR SALIDA", "📊 HISTORIAL"])

    with tab1:
        col_izq, col_der = st.columns(2)
        
        with col_izq:
            st.subheader("Detalles del Gasto")
            fecha = st.date_input("Fecha", value=datetime.now(ZONA_HORARIA).date())
            categoria = st.selectbox("Categoría", [
                "OPERATIVO (Hielo, Gas, Aseo)",
                "MATERIA PRIMA (Urgencias)",
                "TRANSPORTE / DOMICILIOS",
                "MANTENIMIENTO",
                "PERSONAL (Adelantos/Comida)",
                "ADMINISTRATIVO (Papelería)",
                "OTROS"
            ])
            desc = st.text_area("Descripción")
            
        with col_der:
            st.subheader("Valores")
            monto = st.number_input("Valor Pagado ($)", min_value=0, step=1000)
            metodo = st.selectbox("Método de Pago", ["Efectivo (Caja)", "Nequi Empresarial", "Bolsillo Propio"])
            responsable = st.text_input("Responsable")
            foto = st.file_uploader("📸 Foto del Recibo", type=["jpg", "png", "jpeg"])

        if st.button("💾 REGISTRAR GASTO", type="primary", use_container_width=True):
            if monto > 0 and desc and responsable:
                with st.status("Procesando registro...", expanded=True) as status:
                    
                    # 1. SUBIDA A CLOUDINARY
                    url_foto = "Sin Foto"
                    if foto:
                        st.write("📤 Subiendo imagen a Cloudinary...")
                        nombre_cat = categoria.split(" ")[0].upper()
                        # Llamamos a la función de utils
                        resultado_subida = subir_foto_drive(foto, subcarpeta=nombre_cat, carpeta_raiz="GASTOS_VARIABLES")
                        
                        if "Error" in resultado_subida or "http" not in resultado_subida:
                            status.update(label="❌ Error al subir foto", state="error")
                            st.error(f"Detalle del error: {resultado_subida}")
                            return # Detenemos todo si la foto falla
                        else:
                            url_foto = resultado_subida
                    
                    # 2. GUARDADO EN GOOGLE SHEETS
                    st.write("📝 Escribiendo en Google Sheets...")
                    hora_actual = datetime.now(ZONA_HORARIA).strftime("%H:%M")
                    nuevo_gasto = [
                        generar_id(), str(fecha), hora_actual, categoria,
                        desc, float(monto), metodo, responsable, url_foto
                    ]
                    
                    if guardar_gasto(sheet, nuevo_gasto):
                        status.update(label="✅ ¡Gasto Registrado con éxito!", state="complete", expanded=False)
                        st.balloons()
                        time.sleep(2)
                        st.rerun()
                    else:
                        status.update(label="❌ Error al guardar datos", state="error")
            else:
                st.warning("⚠️ Completa los campos obligatorios.")

    with tab2:
        st.subheader("📜 Últimos Movimientos")
        try:
            ws = sheet.worksheet(HOJA_GASTOS)
            df = leer_datos_seguro(ws)
            if not df.empty:
                df["Monto"] = pd.to_numeric(df["Monto"], errors='coerce').fillna(0)
                df_view = df.iloc[::-1].copy()
                st.metric("Total Gastado (Periodo)", formato_moneda_co(df["Monto"].sum()))
                df_view["Monto"] = df_view["Monto"].apply(formato_moneda_co)
                st.dataframe(
                    df_view[["Fecha", "Categoria", "Descripcion", "Monto", "Responsable", "URL_Foto"]],
                    use_container_width=True, hide_index=True,
                    column_config={"URL_Foto": st.column_config.LinkColumn("Ver Recibo")}
                )
            else:
                st.info("No hay gastos registrados.")
        except:
            st.caption("Hoja de gastos no encontrada.")
