import streamlit as st
import pandas as pd
import plotly.express as px
import time
import urllib.parse
from utils import conectar_google_sheets, leer_datos_seguro, generar_id, limpiar_numero, limpiar_cache

# --- CONFIGURACIÓN ---
HOJA_PROVEEDORES = "DB_PROVEEDORES"
HOJA_LOG_COMPRAS = "LOG_COMPRAS"

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return str(valor)

def show(sheet):
    st.title("🤝 Gestión de Proveedores")
    st.caption("Directorio, condiciones comerciales y ranking de aliados.")
    
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
        st.error("Error conectando con la base de datos de proveedores.")
        return

    # TABS ESTILIZADOS
    tab1, tab2, tab3 = st.tabs(["📝 REGISTRO Y EDICIÓN", "📇 FICHA TÉCNICA", "🏆 RANKING"])

    # --- TAB 1: GESTIÓN (FORMULARIO) ---
    with tab1:
        st.markdown("### Configuración de Proveedor")
        col_mode, col_sel = st.columns([1, 2])
        modo = col_mode.radio("Acción:", ["Nuevo", "Editar"], horizontal=True, label_visibility="collapsed")
        
        id_prov = f"PRV-{generar_id()}"
        nombre, categoria, contacto, telefono = "", "General", "", ""
        dias_credito, nit, direccion = 0, "", ""
        
        if modo == "Editar" and not df_prov.empty:
            lista_nombres = sorted(df_prov["Nombre_Empresa"].tolist())
            seleccion = col_sel.selectbox("Seleccionar para editar:", lista_nombres, label_visibility="collapsed")
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

        # Formulario dentro de Card Dorada
        with st.container():
            st.markdown(f'<div class="card-modulo">', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            new_nombre = c1.text_input("Razón Social", value=nombre)
            new_cat = c2.selectbox("Categoría", ["Abarrotes", "Carnes", "Lacteos", "Frutas/Verduras", "Licores", "Empaques", "Servicios", "General"], 
                                    index=0) # Simplificado para el ejemplo
            
            c3, c4 = st.columns(2)
            new_contacto = c3.text_input("Nombre de Contacto", value=contacto)
            new_tel = c4.text_input("WhatsApp / Teléfono", value=telefono)
            
            c5, c6 = st.columns(2)
            new_nit = c5.text_input("NIT / RUT", value=nit)
            new_dias = c6.number_input("Días de Crédito", value=dias_credito, min_value=0)
            
            new_dir = st.text_input("Dirección", value=direccion)
            
            st.write("")
            if st.button("💾 GUARDAR PROVEEDOR", type="primary", use_container_width=True):
                if new_nombre:
                    fila = [id_prov, new_nombre, new_cat, new_contacto, new_tel, new_nit, new_dias, new_dir]
                    if modo == "Nuevo":
                        ws_prov.append_row(fila)
                    else:
                        cell = ws_prov.find(id_prov)
                        ws_prov.update(f"A{cell.row}:H{cell.row}", [fila])
                    st.success("✅ Datos sincronizados."); time.sleep(1); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    # --- TAB 2: FICHA VISUAL PREMIUM ---
    with tab2:
        if not df_prov.empty:
            list_prov = sorted(df_prov['Nombre_Empresa'].unique().tolist())
            seleccion_ficha = st.selectbox("🔍 Buscar proveedor:", list_prov)
            
            if seleccion_ficha:
                info = df_prov[df_prov['Nombre_Empresa'] == seleccion_ficha].iloc[0]
                
                # --- CABECERA DE LA FICHA (DISEÑO DORADO) ---
                st.markdown(f"""
                <div class="card-modulo" style="text-align: left; align-items: flex-start; padding: 30px;">
                    <div style="display: flex; justify-content: space-between; width: 100%;">
                        <div>
                            <h1 style="margin:0; color:#c5a065;">{info['Nombre_Empresa']}</h1>
                            <p style="margin:0; opacity:0.7;">NIT: {info.get('NIT_Rut','S/N')}</p>
                            <span style="background:#580f12; color:white; padding:5px 15px; border-radius:10px; font-size:0.8rem; font-weight:bold;">
                                🚚 {info.get('Categoria','General')}
                            </span>
                        </div>
                        <div style="text-align: right;">
                            <p style="margin:0;"><b>👤 Contacto:</b> {info.get('Nombre_Contacto','S/N')}</p>
                            <p style="margin:0;"><b>📞 WhatsApp:</b> {info.get('Telefono','S/N')}</p>
                            <p style="margin:0; color:#c5a065;"><b>💳 Crédito:</b> {info.get('Dias_Credito', 0)} días</p>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # --- HISTORIAL Y MÉTRICAS ---
                if not df_log.empty and 'Proveedor' in df_log.columns:
                    df_p = df_log[df_log['Proveedor'] == seleccion_ficha].copy()
                    
                    if not df_p.empty:
                        df_p['Total'] = df_p['Precio_Total_Pagado'].apply(limpiar_numero)
                        total_hist = df_p['Total'].sum()
                        deuda = df_p[df_p.get('Estado_Pago','') == 'Pendiente']['Total'].sum() if 'Estado_Pago' in df_p.columns else 0
                        
                        st.write("")
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("Compra Total", formato_moneda(total_hist))
                        m2.metric("Deuda Pendiente", formato_moneda(deuda))
                        m3.metric("N° Facturas", f"{len(df_p)} unds")
                        
                        # Última Fecha
                        try:
                            f_max = pd.to_datetime(df_p['Fecha_Registro']).max()
                            m4.metric("Última Compra", f_max.strftime('%d/%m/%y'))
                        except: m4.metric("Última Compra", "N/A")

                        st.markdown("---")
                        g1, g2 = st.columns([2, 1])
                        with g1:
                            st.markdown("**📦 Historial de facturas:**")
                            st.dataframe(df_p[["Fecha_Registro", "Precio_Total_Pagado", "Metodo_Pago"]].sort_values("Fecha_Registro", ascending=False), 
                                         use_container_width=True, hide_index=True)
                        with g2:
                            # Gráfico circular con colores de la marca
                            fig = px.pie(names=['Pagado', 'Pendiente'], values=[total_hist-deuda, deuda], 
                                         hole=0.6, color_discrete_sequence=['#27ae60', '#580f12'])
                            fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
                            st.plotly_chart(fig, use_container_width=True)

                    else: st.info("Este proveedor aún no tiene compras registradas.")
        else: st.warning("Crea tu primer proveedor en la pestaña de Gestión.")

    # --- TAB 3: RANKING GLOBAL ---
    with tab3:
        st.subheader("🏆 Mejores Aliados Comerciales")
        if not df_log.empty and 'Proveedor' in df_log.columns:
            df_log["Monto"] = pd.to_numeric(df_log["Precio_Total_Pagado"], errors='coerce').fillna(0)
            ranking = df_log.groupby("Proveedor")["Monto"].sum().reset_index().sort_values("Monto", ascending=False).head(10)
            
            fig_rank = px.bar(ranking, x="Monto", y="Proveedor", orientation='h', 
                              color="Monto", color_continuous_scale='YlOrBr',
                              title="Top 10 Proveedores por Volumen de Compra")
            fig_rank.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_rank, use_container_width=True)
        else:
            st.info("Sin datos para generar ranking.")
