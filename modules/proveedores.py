import streamlit as st
import pandas as pd
import plotly.express as px
import time
from utils import conectar_google_sheets, leer_datos_seguro, generar_id, limpiar_numero, limpiar_cache

HOJA_PROVEEDORES = "DB_PROVEEDORES"
HOJA_LOG_COMPRAS = "LOG_COMPRAS"

def show(sheet):
    st.title("🤝 Gestión de Proveedores")
    st.caption("Directorio, condiciones comerciales y ranking.")
    st.markdown("---")
    
    if not sheet: return

    # 1. CARGA DE DATOS
    try:
        ws_prov = sheet.worksheet(HOJA_PROVEEDORES)
        df_prov = leer_datos_seguro(ws_prov)
        
        try:
            ws_compras = sheet.worksheet(HOJA_LOG_COMPRAS)
            df_log = leer_datos_seguro(ws_compras)
        except:
            df_log = pd.DataFrame()
            
    except:
        st.error("Error conectando con la base de datos.")
        return

    # TABS
    tab1, tab2, tab3 = st.tabs(["📝 GESTIÓN (Crear/Editar)", "📇 FICHA & HISTORIAL", "🏆 RANKING"])

    # --- TAB 1: GESTIÓN UNIFICADA ---
    with tab1:
        col_mode, col_sel = st.columns([1, 2])
        modo = col_mode.radio("Acción:", ["Nuevo Proveedor", "Editar Existente"], horizontal=True, label_visibility="collapsed")
        
        # Variables Default
        id_prov = f"PRV-{generar_id()}"
        nombre = ""
        categoria = "General"
        contacto = ""
        telefono = ""
        dias_credito = 0
        nit = ""
        direccion = ""
        
        # MODO EDICIÓN
        if modo == "Editar Existente" and not df_prov.empty:
            lista_nombres = df_prov["Nombre_Empresa"].tolist()
            seleccion = col_sel.selectbox("Seleccionar Proveedor:", lista_nombres)
            
            if seleccion:
                datos = df_prov[df_prov["Nombre_Empresa"] == seleccion].iloc[0]
                id_prov = datos.get("ID_Proveedor", id_prov)
                nombre = datos["Nombre_Empresa"]
                categoria = datos.get("Categoria", "General")
                contacto = datos.get("Nombre_Contacto", "")
                telefono = str(datos.get("Telefono", ""))
                nit = str(datos.get("NIT_Rut", ""))
                direccion = str(datos.get("Direccion", ""))
                dias_credito = int(limpiar_numero(datos.get("Dias_Credito", 0)))

        # FORMULARIO
        with st.container(border=True):
            st.subheader(f"Datos: {nombre if nombre else 'Nuevo Aliado'}")
            
            c1, c2 = st.columns(2)
            new_nombre = c1.text_input("Nombre Empresa / Razón Social", value=nombre)
            new_cat = c2.selectbox("Categoría Principal", ["Abarrotes", "Carnes", "Lacteos", "Frutas/Verduras", "Licores", "Empaques", "Servicios", "General"], index=["Abarrotes", "Carnes", "Lacteos", "Frutas/Verduras", "Licores", "Empaques", "Servicios", "General"].index(categoria) if categoria in ["Abarrotes", "Carnes", "Lacteos", "Frutas/Verduras", "Licores", "Empaques", "Servicios", "General"] else 7)
            
            c3, c4 = st.columns(2)
            new_contacto = c3.text_input("Nombre del Vendedor", value=contacto)
            new_tel = c4.text_input("WhatsApp / Teléfono", value=telefono)
            
            c5, c6 = st.columns(2)
            new_nit = c5.text_input("NIT / Cédula", value=nit)
            new_dias = c6.number_input("Días de Crédito (0 = Contado)", value=dias_credito, min_value=0, step=1, help="Días que nos dan para pagar")
            
            new_dir = st.text_input("Dirección Física", value=direccion)

            st.write("")
            if st.button("💾 GUARDAR DATOS", type="primary", use_container_width=True):
                if new_nombre:
                    try:
                        # Estructura: ID, Nombre, Categoria, Contacto, Telefono, NIT, Dias, Direccion
                        fila = [id_prov, new_nombre, new_cat, new_contacto, new_tel, new_nit, new_dias, new_dir]
                        
                        if modo == "Nuevo Proveedor":
                            ws_prov.append_row(fila)
                            st.success("✅ Proveedor Creado.")
                        else:
                            cell = ws_prov.find(id_prov)
                            rango = f"A{cell.row}:H{cell.row}"
                            ws_prov.update(rango, [fila])
                            st.success("✅ Proveedor Actualizado.")
                        
                        limpiar_cache()
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error guardando: {e}")
                else:
                    st.warning("El nombre es obligatorio.")

    # --- TAB 2: FICHA VISUAL ---
    with tab2:
        if not df_prov.empty:
            list_prov = sorted(df_prov['Nombre_Empresa'].unique().tolist())
            seleccion_ficha = st.selectbox("🔍 Ver Ficha de:", list_prov, key="sel_ficha")
            
            if seleccion_ficha:
                info = df_prov[df_prov['Nombre_Empresa'] == seleccion_ficha].iloc[0]
                
                # Tarjeta de Contacto
                with st.container(border=True):
                    c1, c2, c3 = st.columns([1, 2, 2])
                    with c1: st.markdown("# 🏢")
                    with c2:
                        st.subheader(info['Nombre_Empresa'])
                        st.caption(f"NIT: {info.get('NIT_Rut','S/N')}")
                        st.write(f"🚚 **{info.get('Categoria','Variado')}**")
                    with c3:
                        st.write(f"👤 {info.get('Nombre_Contacto','S/N')}")
                        st.write(f"📞 {info.get('Telefono','S/N')}")
                        cred = info.get('Dias_Credito', 0)
                        st.info(f"💳 Crédito: **{cred} días**")

                # Historial de Compras
                if not df_log.empty and 'Proveedor' in df_log.columns:
                    df_p = df_log[df_log['Proveedor'] == seleccion_ficha].copy()
                    
                    if not df_p.empty:
                        st.markdown("---")
                        df_p['Total'] = df_p['Precio_Total_Pagado'].apply(limpiar_numero)
                        total_hist = df_p['Total'].sum()
                        
                        # --- CÁLCULO DE ÚLTIMA FECHA ---
                        try:
                            df_p['Fecha_DT'] = pd.to_datetime(df_p['Fecha_Registro'], errors='coerce')
                            fecha_max = df_p['Fecha_DT'].max()
                            if pd.notnull(fecha_max):
                                meses = {1:"Ene", 2:"Feb", 3:"Mar", 4:"Abr", 5:"May", 6:"Jun", 7:"Jul", 8:"Ago", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Dic"}
                                ult_compra = f"{fecha_max.day}-{meses[fecha_max.month]}-{fecha_max.year}"
                            else:
                                ult_compra = "N/A"
                        except:
                            ult_compra = "N/A"

                        # Deuda
                        deuda = 0
                        if 'Estado_Pago' in df_p.columns:
                            deuda = df_p[df_p['Estado_Pago'] == 'Pendiente']['Total'].sum()
                        
                        # KPIs (4 Columnas)
                        k1, k2, k3, k4 = st.columns(4)
                        k1.metric("Gasto Histórico", f"${total_hist:,.0f}")
                        k2.metric("Deuda Actual", f"${deuda:,.0f}", delta_color="inverse")
                        k3.metric("N° Facturas", len(df_p))
                        k4.metric("Última Compra", ult_compra) # <--- AQUÍ ESTÁ DE VUELTA
                        
                        # Gráficos
                        g1, g2 = st.columns(2)
                        with g1:
                            if total_hist > 0:
                                pagado = total_hist - deuda
                                fig1 = px.pie(names=['Pagado', 'Deuda'], values=[pagado, deuda], 
                                            title="Estado de Cuenta",
                                            color=['Pagado', 'Deuda'], 
                                            color_discrete_map={'Pagado':'#27ae60', 'Deuda':'#c0392b'}, hole=0.5)
                                st.plotly_chart(fig1, use_container_width=True)
                        
                        with g2:
                            st.write("📦 **Productos más comprados:**")
                            if 'Nombre_Insumo' in df_p.columns:
                                top_prods = df_p['Nombre_Insumo'].value_counts().head(5)
                                st.dataframe(top_prods, use_container_width=True)

                    else: st.info("No hay compras registradas a este proveedor.")
        else: st.warning("No hay proveedores creados.")

    # --- TAB 3: RANKING GLOBAL ---
    with tab3:
        st.subheader("🏆 Ranking de Proveedores")
        if not df_log.empty and 'Proveedor' in df_log.columns:
            # Limpieza
            df_log["Precio_Total_Pagado"] = pd.to_numeric(df_log["Precio_Total_Pagado"], errors='coerce').fillna(0)
            
            # Agrupar
            ranking = df_log.groupby("Proveedor")["Precio_Total_Pagado"].sum().reset_index()
            ranking = ranking.sort_values("Precio_Total_Pagado", ascending=False)
            
            # Gráfico
            fig_rank = px.bar(ranking, x="Precio_Total_Pagado", y="Proveedor", orientation='h', 
                              text_auto='$,.0f', title="¿A quién le compramos más?", color="Precio_Total_Pagado")
            st.plotly_chart(fig_rank, use_container_width=True)
        else:
            st.info("Registra compras para ver el ranking.")