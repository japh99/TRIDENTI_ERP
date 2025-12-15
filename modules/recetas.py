import streamlit as st
import pandas as pd
import requests
import os
import json
import time
from utils import leer_datos_seguro, limpiar_numero

# --- FUNCIÓN PARA ESCRIBIR EN LOYVERSE (NUEVO) ---
def actualizar_precio_loyverse(variant_id, nuevo_precio):
    """Envía el nuevo precio a la API de Loyverse"""
    try:
        # 1. Obtener Token
        token = os.environ.get('LOYVERSE_TOKEN')
        if not token:
            return False, "No hay Token de Loyverse configurado."
            
        # 2. Configurar la petición PUT (Actualizar)
        url = f"https://api.loyverse.com/v1.0/variants/{variant_id}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {
            "default_price": nuevo_precio
        }
        
        # 3. Enviar
        response = requests.put(url, headers=headers, json=payload)
        
        if response.status_code == 200:
            return True, "Éxito"
        else:
            return False, f"Error API: {response.text}"
            
    except Exception as e:
        return False, str(e)

# --- MÓDULO PRINCIPAL ---
def show(sheet):
    st.header("🍲 Ingeniería de Menú & Precios")
    
    try:
        hoja_recetas = sheet.worksheet("DB_RECETAS")
        hoja_menu = sheet.worksheet("DB_MENU_LOYVERSE") # Necesitamos la hoja para actualizar el precio local también
        df_menu = leer_datos_seguro(hoja_menu)
        df_insumos = leer_datos_seguro(sheet.worksheet("DB_INSUMOS"))
        df_recetas = leer_datos_seguro(hoja_recetas)
    except: 
        st.error("Error cargando bases de datos.")
        return

    list_platos = df_menu['Nombre_Plato'].tolist() if not df_menu.empty else []
    plato = st.selectbox("Selecciona Plato:", list_platos)

    if plato:
        # Obtener info del plato
        # Usamos el index para poder actualizar luego la hoja local
        idx_plato = df_menu[df_menu['Nombre_Plato'] == plato].index[0]
        info = df_menu.iloc[idx_plato]
        
        id_plato = info['ID_Variant']
        precio_actual = limpiar_numero(info['Precio_Venta'])
        
        # --- ESTRUCTURA DE 2 COLUMNAS ---
        st.markdown("---")
        c1, c2 = st.columns([2, 1])
        
        # === COLUMNA IZQUIERDA: INGREDIENTES Y COSTOS ===
        with c1:
            st.subheader(f"🛠️ Receta: {plato}")
            # Filtro Ingredientes
            if not df_recetas.empty and 'ID_Plato_Loyverse' in df_recetas.columns:
                ing_plato = df_recetas[df_recetas['ID_Plato_Loyverse'] == id_plato]
            else: ing_plato = pd.DataFrame(columns=df_recetas.columns)

            col_ver = ['Nombre_Insumo_Visual', 'Cantidad_Neta_Gr', 'ID_Insumo', 'ID_Plato_Loyverse', 'Nombre_Plato_Visual']
            for c in col_ver: 
                if c not in ing_plato.columns: ing_plato[c] = ""

            # Editor
            edited_df = st.data_editor(
                ing_plato[col_ver], 
                num_rows="dynamic", use_container_width=True, hide_index=True,
                column_config={
                    "ID_Insumo": st.column_config.TextColumn(disabled=True),
                    "ID_Plato_Loyverse": st.column_config.TextColumn(disabled=True),
                    "Nombre_Plato_Visual": st.column_config.TextColumn(disabled=True),
                    "Nombre_Insumo_Visual": st.column_config.TextColumn(disabled=True, label="Insumo"),
                    "Cantidad_Neta_Gr": st.column_config.NumberColumn(label="Cant (Gr/Un)", min_value=0, step=1)
                }, key="recetas_ed"
            )

            if st.button("💾 GUARDAR CAMBIOS RECETA"):
                if not df_recetas.empty:
                    df_otras = df_recetas[df_recetas['ID_Plato_Loyverse'] != id_plato]
                else: df_otras = pd.DataFrame(columns=df_recetas.columns)
                
                if not edited_df.empty:
                    edited_df['ID_Plato_Loyverse'] = id_plato
                    edited_df['Nombre_Plato_Visual'] = plato
                    edited_df['Costo_Calculado_Linea'] = "Auto"
                
                df_final = pd.concat([df_otras, edited_df], ignore_index=True)
                d = [df_final.columns.tolist()] + df_final.values.tolist()
                hoja_recetas.clear()
                hoja_recetas.update(range_name="A1", values=d)
                st.success("Actualizado")
                st.rerun()
            
            # Agregar Ingrediente Rápido
            with st.expander("➕ Agregar Ingrediente Nuevo"):
                cc1, cc2 = st.columns([3,1])
                lista = df_insumos['Nombre_Insumo'] + " | " + df_insumos['ID_Insumo']
                ins = cc1.selectbox("Insumo", lista)
                cant = cc2.number_input("Cantidad", 0.0)
                if st.button("Agregar"):
                    idi = ins.split(" | ")[1]
                    nom = ins.split(" | ")[0]
                    hoja_recetas.append_row([id_plato, plato, idi, nom, cant, "Auto"])
                    st.rerun()

        # === COLUMNA DERECHA: SIMULADOR DE PRECIOS ===
        with c2:
            st.subheader("💰 Estrategia de Precios")
            
            # 1. Calcular Costo Actual
            costo_total = 0
            if not edited_df.empty:
                for _, row in edited_df.iterrows():
                    try:
                        cant = limpiar_numero(row['Cantidad_Neta_Gr'])
                        id_i = row['ID_Insumo']
                        dat = df_insumos[df_insumos['ID_Insumo'] == id_i]
                        if not dat.empty:
                            cu = limpiar_numero(dat.iloc[0]['Costo_Promedio_Ponderado'])
                            costo_total += cant * cu
                    except: pass
            
            # Mostrar Costo
            st.info(f"Costo Materia Prima: **${costo_total:,.0f}**")
            
            st.markdown("---")
            st.write("🎯 **Simulador de Margen**")
            
            # 2. Simulador
            margen_deseado = st.slider("Tu Meta de Margen (%)", 0, 99, 35)
            
            # Matemática: Precio = Costo / (1 - %Margen)
            if margen_deseado < 100:
                precio_sugerido = costo_total / (1 - (margen_deseado/100))
            else:
                precio_sugerido = 0
            
            st.metric("Precio Sugerido", f"${precio_sugerido:,.0f}")
            
            # Comparativa visual
            diferencia = precio_actual - precio_sugerido
            color_delta = "normal" if diferencia >= 0 else "inverse" # Verde si cobras más que el sugerido
            
            st.metric("Precio Actual (Loyverse)", f"${precio_actual:,.0f}", 
                      delta=f"${diferencia:,.0f} vs Sugerido",
                      delta_color=color_delta)
            
            st.markdown("---")
            st.write("👇 **ACTUALIZAR REALIDAD**")
            
            nuevo_precio_input = st.number_input("Nuevo Precio Venta", value=float(precio_sugerido), step=500.0)
            
            if st.button("🚀 ENVIAR A LOYVERSE", type="primary"):
                if nuevo_precio_input > 0:
                    with st.spinner("Conectando con Loyverse..."):
                        exito, msg = actualizar_precio_loyverse(id_plato, nuevo_precio_input)
                        
                        if exito:
                            st.success(f"✅ ¡Precio actualizado a ${nuevo_precio_input:,.0f}!")
                            
                            # Actualizar también el Excel local para que no tengas que sincronizar todo
                            # Fila es idx_plato + 2 (por encabezado y base 1 de sheets)
                            # Columna 5 es Precio_Venta (A,B,C,D,E)
                            hoja_menu.update_cell(idx_plato + 2, 5, nuevo_precio_input)
                            
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error(f"Fallo al actualizar: {msg}")