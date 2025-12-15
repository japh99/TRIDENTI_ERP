import streamlit as st
import time
from utils import generar_id, leer_datos_seguro, limpiar_numero

def show(sheet):
    st.header("📦 Maestro de Insumos")
    hoja = sheet.worksheet("DB_INSUMOS")
    
    tab1, tab2 = st.tabs(["📝 CREAR NUEVO", "✏️ GESTIONAR"])
    
    # --- CREACIÓN INTERACTIVA (SIN BLOQUEO) ---
    with tab1:
        st.info("ℹ️ Ingresa los datos tal cual los compras.")
        
        c1, c2 = st.columns(2)
        nombre = c1.text_input("Nombre del Insumo", placeholder="Ej: Pan Brioche, Tomate")
        cat = c2.selectbox("Categoría", ["Abarrotes", "Carnicos", "Lacteos", "Verduras", "Bebidas", "Empaques", "Licores"])
        
        st.markdown("---")
        st.write("### 📏 Configuración de Medida")
        
        tipo = st.radio("Tipo:", ["PESO (Kg/Lb)", "VOLUMEN (Lt/Ml)", "UNIDADES (Paquetes/Cajas)"], horizontal=True)
        
        factor = 0
        unidad_txt = ""
        
        c3, c4 = st.columns(2)
        
        if "PESO" in tipo:
            uni = c3.selectbox("Unidad", ["Kilo (1kg)", "Libra (500g)", "Arroba (12.5kg)", "Bulto (50kg)", "Bulto (25kg)", "Gramo"])
            cant = c4.number_input("Cantidad Comprada", 1.0)
            base = 1000
            if "Libra" in uni: base = 500
            elif "Arroba" in uni: base = 12500
            elif "Bulto (50" in uni: base = 50000
            elif "Bulto (25" in uni: base = 25000
            elif "Gramo" in uni: base = 1
            factor = base * cant
            unidad_txt = uni
            
        elif "VOLUMEN" in tipo:
            uni = c3.selectbox("Unidad", ["Litro (1000ml)", "Galón (3.75L)", "Botella (750ml)", "Ml"])
            cant = c4.number_input("Cantidad Comprada", 1.0)
            base = 1000
            if "Galón" in uni: base = 3785
            elif "Botella" in uni: base = 750
            elif "Ml" in uni: base = 1
            factor = base * cant
            unidad_txt = uni
            
        elif "UNIDADES" in tipo:
            es_pack = c3.checkbox("¿Viene en Paquete?", value=True)
            if es_pack:
                u_pack = c3.number_input("Unidades por Paquete", 1, value=10)
                cant = c4.number_input("¿Cuántos paquetes?", 1)
                factor = u_pack * cant
                unidad_txt = f"Paquete x{u_pack}"
            else:
                factor = c4.number_input("Total Unidades Sueltas", 1)
                unidad_txt = "Unidad Suelta"

        st.markdown("---")
        c5, c6 = st.columns(2)
        precio = c5.number_input("💰 Precio TOTAL Pagado ($)", step=1000.0)
        merma = c6.slider("% Merma", 0, 100, 0)
        
        # CÁLCULO EN VIVO
        costo_u = 0
        if precio > 0 and factor > 0:
            costo_u = precio / factor
            
        st.success(f"📊 **RESUMEN:**\nEntrada Real: {factor:,.0f} (Gr/Ml/Unid) | Costo Unitario: **${costo_u:,.2f}**")
        
        if st.button("💾 GUARDAR INSUMO", type="primary"):
            if nombre and precio > 0:
                nid = f"INS-{generar_id()}"
                # 10 Columnas exactas
                row = [nid, nombre.upper(), cat, unidad_txt, factor, precio, 0, 0, costo_u, merma/100]
                hoja.append_row(row)
                st.balloons()
                st.success("Creado!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Falta Nombre o Precio.")

    # --- EDICIÓN ---
    with tab2:
        df = leer_datos_seguro(hoja)
        if not df.empty:
            df_ed = st.data_editor(df, num_rows="dynamic", use_container_width=True, key="ins_ed")
            
            c_a, c_b = st.columns(2)
            if c_a.button("💾 GUARDAR CAMBIOS"):
                d = [df_ed.columns.tolist()] + df_ed.values.tolist()
                hoja.clear()
                hoja.update(range_name="A1", values=d)
                st.success("Guardado")
                st.rerun()
                
            if c_b.button("🔄 RECALCULAR PRECIOS"):
                for i, r in df_ed.iterrows():
                    try:
                        p = limpiar_numero(r.get('Costo_Ultima_Compra', 0))
                        f = limpiar_numero(r.get('Factor_Conversion_Gr', 1))
                        if f > 0: df_ed.at[i, 'Costo_Promedio_Ponderado'] = p / f
                    except: pass
                d = [df_ed.columns.tolist()] + df_ed.values.tolist()
                hoja.clear()
                hoja.update(range_name="A1", values=d)
                st.success("Recalculado")
                st.rerun()