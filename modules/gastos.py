import streamlit as st
import pandas as pd
import time
from datetime import datetime
import pytz
from utils import conectar_google_sheets, subir_foto_drive, generar_id, leer_datos_seguro, ZONA_HORARIA

# --- CONFIGURACIÓN ---
HOJA_GASTOS = "LOG_GASTOS"

def formato_moneda_co(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return str(valor)

def guardar_gasto(sheet, datos):
    try:
        try: ws = sheet.worksheet(HOJA_GASTOS)
        except:
            ws = sheet.add_worksheet(title=HOJA_GASTOS, rows="1000", cols="10")
            ws.append_row(["ID_Gasto", "Fecha", "Hora", "Categoria", "Descripcion", "Monto", "Metodo_Pago", "Responsable", "URL_Foto"])
        
        ws.append_row([datos])
        return True
    except Exception as e:
        st.error(f"Error guardando: {e}")
        return False

def show(sheet):
    st.title("💸 Gastos Variables & Caja Menor")
    st.caption("Registro de salidas operativas del día a día (Taxis, Hielo, Aseo, etc).")
    st.markdown("---")
    
    if not sheet: return

    tab1, tab2 = st.tabs(["📝 REGISTRAR SALIDA", "📊 HISTORIAL"])

    with tab1:
        col_izq, col_der = st.columns(2)
        
        with col_izq:
            st.subheader("Detalles del Gasto")
            fecha_hoy = datetime.now(ZONA_HORARIA).date()
            fecha = st.date_input("Fecha", value=fecha_hoy)
            
            # Categorías
            categoria = st.selectbox("Categoría", [
                "OPERATIVO (Hielo, Gas, Aseo)",
                "MATERIA PRIMA (Urgencias)",
                "TRANSPORTE / DOMICILIOS",
                "MANTENIMIENTO",
                "PERSONAL (Adelantos/Comida)",
                "ADMINISTRATIVO (Papelería)",
                "OTROS"
            ])
            
            desc = st.text_area("Descripción", placeholder="Ej: Taxi para llevar pedido a la 80")
            
        with col_der:
            st.subheader("Valores")
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
                        # ORGANIZACIÓN DE CARPETAS EN CLOUD
                        # Carpeta Raíz: GASTOS_VARIABLES
                        # Subcarpeta: TRANSPORTE, OPERATIVO, etc.
                        nombre_carpeta = categoria.split(" ")[0].upper() # Toma la primera palabra (OPERATIVO, TRANSPORTE...)
                        
                        url_foto = subir_foto_drive(foto, subcarpeta=nombre_carpeta, carpeta_raiz="GASTOS_VARIABLES")
                    
                    if "Error" in url_foto:
                        status.update(label="❌ Error en foto", state="error")
                        st.error(url_foto)
                    else:
                        st.write("Guardando en base de datos...")
                        hora_actual = datetime.now(ZONA_HORARIA).strftime("%H:%M")
                        
                        nuevo_gasto = [
                            generar_id(),
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
                            st.balloons()
                            st.success(f"✅ Gasto de {formato_moneda_co(monto)} registrado.")
                            time.sleep(2)
                            st.rerun()
                        else:
                            status.update(label="Error al guardar en Sheets", state="error")
            else:
                st.warning("⚠️ Faltan datos obligatorios (Monto, Descripción o Responsable).")

    with tab2:
        st.subheader("📜 Últimos Movimientos")
        try:
            ws = sheet.worksheet(HOJA_GASTOS)
            df = leer_datos_seguro(ws)
            
            if not df.empty:
                df = df.iloc[::-1] # Orden inverso
                
                # KPIs
                total_gastado = pd.to_numeric(df["Monto"], errors='coerce').sum()
                st.metric("Total Gastado (Histórico)", formato_moneda_co(total_gastado))
                
                if "Monto" in df.columns:
                    df["Monto"] = pd.to_numeric(df["Monto"], errors='coerce').apply(formato_moneda_co)

                st.dataframe(
                    df[["Fecha", "Categoria", "Descripcion", "Monto", "Responsable", "URL_Foto"]],
                    use_container_width=True,
                    hide_index=True,
                    column_config={"URL_Foto": st.column_config.LinkColumn("Ver Recibo")}
                )
            else:
                st.info("No hay gastos registrados.")
        except:
            st.caption("Aún no se ha creado la hoja de gastos.")