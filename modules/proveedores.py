import streamlit as st
import pandas as pd
import plotly.express as px
from utils import leer_datos_seguro, generar_id, limpiar_numero
from datetime import datetime

def show(sheet):
    st.header("🤝 Directorio y Gestión de Proveedores")
    
    try:
        hoja_prov = sheet.worksheet("DB_PROVEEDORES")
        hoja_log = sheet.worksheet("LOG_COMPRAS")
        df_prov = leer_datos_seguro(hoja_prov)
        df_log = leer_datos_seguro(hoja_log)
        
        if not df_prov.empty: df_prov.columns = df_prov.columns.str.strip()
        if not df_log.empty: df_log.columns = df_log.columns.str.strip()
            
    except: return

    tab_ficha, tab_crear, tab_edit = st.tabs(["📇 FICHA TÉCNICA", "➕ NUEVO PROVEEDOR", "✏️ EDITAR"])

    with tab_ficha:
        if not df_prov.empty:
            list_prov = sorted(df_prov['Nombre_Empresa'].unique().tolist())
            seleccion = st.selectbox("🔍 Buscar Proveedor:", list_prov)
            
            if seleccion:
                info = df_prov[df_prov['Nombre_Empresa'] == seleccion].iloc[0]
                
                with st.container(border=True):
                    c1, c2, c3 = st.columns([1, 2, 2])
                    with c1: st.markdown("## 🏢")
                    with c2:
                        st.subheader(info['Nombre_Empresa'])
                        st.caption(f"ID: {info.get('ID_Proveedor','')}")
                        st.write(f"🚚 {info.get('Categoria_Principal','Variado')}")
                    with c3:
                        st.write(f"👤 {info.get('Nombre_Contacto','S/N')}")
                        st.write(f"📞 {info.get('Telefono_Pedidos','S/N')}")
                        st.write(f"📍 {info.get('Direccion_Fisica','S/N')}")

                if not df_log.empty and 'Proveedor' in df_log.columns:
                    df_p = df_log[df_log['Proveedor'] == seleccion].copy()
                    
                    if not df_p.empty:
                        st.markdown("---")
                        
                        # --- FECHA CORTA ---
                        df_p['Fecha_DT'] = pd.to_datetime(df_p['Fecha_Registro'])
                        fecha_max = df_p['Fecha_DT'].max()
                        
                        # Formato corto: 13-Dic-2025
                        meses_es = {1:"Ene", 2:"Feb", 3:"Mar", 4:"Abr", 5:"May", 6:"Jun", 
                                   7:"Jul", 8:"Ago", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Dic"}
                        
                        ult_compra_txt = f"{fecha_max.day}-{meses_es[fecha_max.month]}-{fecha_max.year}"
                        
                        # KPIs
                        df_p['Total'] = df_p['Precio_Total_Pagado'].apply(limpiar_numero)
                        total_hist = df_p['Total'].sum()
                        deuda = 0
                        if 'Estado_Pago' in df_p.columns:
                            deuda = df_p[df_p['Estado_Pago'] == 'Pendiente']['Total'].sum()
                        
                        k1, k2, k3, k4 = st.columns(4)
                        k1.metric("Gasto Histórico", f"${total_hist:,.0f}")
                        k2.metric("Deuda Actual", f"${deuda:,.0f}", delta_color="inverse")
                        k3.metric("N° Facturas", len(df_p))
                        k4.metric("Última Compra", ult_compra_txt)
                        
                        # PRODUCTOS
                        st.write("📦 **Productos:**")
                        prods = sorted(df_p['Nombre_Insumo'].unique().tolist())
                        html_badges = "".join([f"<span style='background-color:#f0f2f6;color:#31333F;padding:4px 10px;border-radius:12px;margin-right:5px;border:1px solid #ddd;display:inline-block;margin-bottom:5px;font-size:12px'>{p}</span>" for p in prods])
                        st.markdown(html_badges, unsafe_allow_html=True)
                        
                        st.markdown("---")

                        # GRÁFICOS
                        g1, g2 = st.columns(2)
                        with g1:
                            st.caption("Estado de Pagos")
                            if total_hist > 0:
                                pagado = total_hist - deuda
                                fig1 = px.pie(names=['Pagado', 'Deuda'], values=[pagado, deuda], 
                                            color=['Pagado', 'Deuda'], 
                                            color_discrete_map={'Pagado':'#27ae60', 'Deuda':'#c0392b'}, hole=0.5)
                                fig1.update_layout(height=220, margin=dict(t=0,b=0,l=0,r=0))
                                st.plotly_chart(fig1, use_container_width=True)
                        
                        with g2:
                            st.caption("Métodos de Pago")
                            if 'Metodo_Pago' in df_p.columns:
                                df_met = df_p.groupby('Metodo_Pago')['Total'].sum().reset_index()
                                fig2 = px.bar(df_met, x='Total', y='Metodo_Pago', orientation='h', color='Metodo_Pago')
                                fig2.update_layout(height=220, showlegend=False, margin=dict(t=0,b=0,l=0,r=0))
                                st.plotly_chart(fig2, use_container_width=True)

                        # TABLA
                        with st.expander("📜 Historial Detallado", expanded=True):
                            cols_ver = ['Fecha_Registro', 'Numero_Factura', 'Nombre_Insumo', 'Cantidad_Compra_Original', 'Unidad_Original', 'Precio_Total_Pagado', 'Estado_Pago', 'Link_Foto_Factura']
                            cols_ok = [c for c in cols_ver if c in df_p.columns]
                            st.dataframe(df_p[cols_ok].sort_values('Fecha_Registro', ascending=False), use_container_width=True, hide_index=True)
                    else: st.info("Sin compras.")
                else: st.warning("Historial vacío.")
        else: st.warning("Crea proveedores.")

    with tab_crear:
        with st.form("add_prov"):
            c1, c2 = st.columns(2)
            emp = c1.text_input("Nombre Empresa")
            con = c2.text_input("Contacto")
            tel = c1.text_input("Teléfono")
            dir = c2.text_input("Dirección")
            cat = c1.selectbox("Cat", ["Fruver", "Carnes", "Abarrotes", "Lácteos", "Bebidas", "Varios"])
            dias = c2.multiselect("Días", ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"])
            if st.form_submit_button("💾 GUARDAR"):
                if emp:
                    hoja_prov.append_row([f"PROV-{generar_id()}", emp, con, tel, cat, str(dias), dir])
                    st.success("Creado!")
                    st.rerun()
                else: st.error("Falta nombre.")

    with tab_edit:
        if not df_prov.empty:
            df_edit = st.data_editor(df_prov, num_rows="dynamic", use_container_width=True)
            if st.button("💾 GUARDAR CAMBIOS"):
                d = [df_edit.columns.tolist()] + df_edit.values.tolist()
                hoja_prov.clear()
                hoja_prov.update(range_name="A1", values=d)
                st.success("Actualizado")
                st.rerun()