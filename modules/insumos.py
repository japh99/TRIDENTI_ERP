import streamlit as st
import pandas as pd
import plotly.express as px
import time
from utils import conectar_google_sheets, leer_datos_seguro, generar_id, limpiar_numero, limpiar_cache

HOJA_INSUMOS = "DB_INSUMOS"
HOJA_LOG_COMPRAS = "LOG_COMPRAS"

# ESTRUCTURA MAESTRA
ENCABEZADOS_OFICIALES = [
    "ID_Insumo", "Nombre_Insumo", "Categoria", "Unidad_Compra", 
    "Factor_Conversion_Gr", "Costo_Ultima_Compra", "Stock_Actual_Gr", 
    "Stock_Minimo_Gr", "Costo_Promedio_Ponderado", "Merma_Porcentaje", 
    "Proveedor_Sugerido"
]

def reparar_encabezados(sheet):
    try:
        ws = sheet.worksheet(HOJA_INSUMOS)
        ws.update("A1:K1", [ENCABEZADOS_OFICIALES])
        return True
    except Exception as e:
        st.error(f"Error reparando DB: {e}")
        return False

def show(sheet):
    st.title("📦 Maestro de Insumos")
    st.caption("Administración inteligente de inventario.")
    st.markdown("---")
    
    if not sheet: return

    try:
        ws = sheet.worksheet(HOJA_INSUMOS)
        df = leer_datos_seguro(ws)
        
        try:
            ws_compras = sheet.worksheet(HOJA_LOG_COMPRAS)
            df_compras = leer_datos_seguro(ws_compras)
        except:
            df_compras = pd.DataFrame()
    except: 
        st.error("Error conectando con la base de datos.")
        return

    tab1, tab2, tab3 = st.tabs(["📝 FICHA TÉCNICA", "📊 VISOR DE STOCK", "📈 TENDENCIAS"])

    # --- TAB 1: GESTIÓN ---
    with tab1:
        col_mode, col_sel = st.columns([1, 2])
        modo = col_mode.radio("Acción:", ["Crear Nuevo", "Editar Existente"], horizontal=True, label_visibility="collapsed")
        
        # Variables Default
        id_ins = f"INS-{generar_id()}"
        nombre = ""
        cat = "Abarrotes"
        tipo_medida = "Unidad (Pieza/Paquete)"
        contenido_paquete = 1.0
        stock_actual = 0.0
        stock_minimo = 0.0
        costo_referencia = 0.0
        merma = 0.0
        
        # Variable Auto-calculada
        mejor_proveedor_calc = "General" 
        
        if modo == "Editar Existente" and not df.empty:
            lista_nombres = sorted(df["Nombre_Insumo"].unique().tolist())
            seleccion = col_sel.selectbox("Buscar Insumo:", lista_nombres)
            
            if seleccion:
                datos = df[df["Nombre_Insumo"] == seleccion].iloc[0]
                id_ins = datos["ID_Insumo"]
                nombre = datos["Nombre_Insumo"]
                cat = datos["Categoria"]
                
                factor_bd = limpiar_numero(datos["Factor_Conversion_Gr"])
                stock_actual_bd = limpiar_numero(datos["Stock_Actual_Gr"])
                stock_minimo_bd = limpiar_numero(datos["Stock_Minimo_Gr"])
                costo_referencia = limpiar_numero(datos.get("Costo_Ultima_Compra", 0))
                merma = limpiar_numero(datos.get("Merma_Porcentaje", 0))
                mejor_proveedor_calc = datos.get("Proveedor_Sugerido", "General")
                
                uni_str = str(datos["Unidad_Compra"])
                if "Kilo" in uni_str or "Libra" in uni_str or "Gramo" in uni_str: tipo_medida = "Peso (Kg/Lb)"
                elif "Litro" in uni_str or "Galón" in uni_str or "Ml" in uni_str: tipo_medida = "Volumen (Lt/Ml)"
                else: tipo_medida = "Unidad (Pieza/Paquete)"
                
                if factor_bd > 0:
                    stock_actual = stock_actual_bd / factor_bd
                    stock_minimo = stock_minimo_bd / factor_bd
                    contenido_paquete = factor_bd
                else:
                    contenido_paquete = 1.0

        with st.container(border=True):
            
            # --- 🧠 SECCIÓN DE INTELIGENCIA (EL CAMBIO) ---
            if modo == "Editar Existente" and nombre:
                st.subheader("🧠 Inteligencia de Abastecimiento")
                
                if not df_compras.empty and "Nombre_Insumo" in df_compras.columns:
                    # 1. Filtrar compras de este insumo
                    hist = df_compras[df_compras["Nombre_Insumo"] == nombre].copy()
                    
                    if not hist.empty:
                        # 2. Calcular precio unitario
                        hist["Total"] = pd.to_numeric(hist["Precio_Total_Pagado"], errors='coerce')
                        hist["Cant"] = pd.to_numeric(hist["Cantidad_Compra_Original"], errors='coerce')
                        hist["Precio_Unit"] = hist["Total"] / hist["Cant"]
                        
                        # 3. Ranking
                        ranking = hist.groupby("Proveedor")["Precio_Unit"].mean().reset_index().sort_values("Precio_Unit")
                        
                        # Obtener datos
                        lista_provs = ranking["Proveedor"].tolist()
                        top_1 = ranking.iloc[0]["Proveedor"]
                        precio_top = ranking.iloc[0]["Precio_Unit"]
                        
                        # Actualizar variable para guardar
                        mejor_proveedor_calc = top_1
                        
                        # 4. Mostrar Tarjetas Visuales
                        kpi1, kpi2 = st.columns(2)
                        
                        with kpi1:
                            st.info(f"📋 **Proveedores Relacionados:**\n\n{', '.join(lista_provs)}")
                            
                        with kpi2:
                            st.success(f"🏆 **Mejor Opción:**\n\n**{top_1}** (${precio_top:,.0f} prom)")
                            
                    else:
                        st.caption("Aún no tienes compras registradas de este producto para analizar proveedores.")
                else:
                    st.caption("Registra compras para activar la inteligencia de proveedores.")
                
                st.markdown("---")

            # --- FORMULARIO NORMAL ---
            st.subheader(f"Ficha: {nombre if nombre else 'Nuevo'}")
            
            c1, c2 = st.columns(2)
            new_nombre = c1.text_input("Nombre del Insumo", value=nombre)
            new_cat = c2.selectbox("Categoría", ["Abarrotes", "Carnes", "Lacteos", "Frutas/Verduras", "Licores", "Empaques", "Aseo"], index=["Abarrotes", "Carnes", "Lacteos", "Frutas/Verduras", "Licores", "Empaques", "Aseo"].index(cat) if cat in ["Abarrotes", "Carnes", "Lacteos", "Frutas/Verduras", "Licores", "Empaques", "Aseo"] else 0)

            st.write("📏 **Medidas**")
            tipo_sel = st.radio("Tipo:", ["Unidad (Pieza/Paquete)", "Peso (Kg/Lb)", "Volumen (Lt/Ml)"], 
                                horizontal=True, index=["Unidad (Pieza/Paquete)", "Peso (Kg/Lb)", "Volumen (Lt/Ml)"].index(tipo_medida))
            
            col_u1, col_u2 = st.columns(2)
            factor_final = 1.0
            unidad_final = "Unidad"
            
            if tipo_sel == "Unidad (Pieza/Paquete)":
                es_paquete = col_u1.checkbox("¿Viene en Paquete/Caja?", value=(contenido_paquete > 1))
                if es_paquete:
                    cant_paq = col_u2.number_input("Unds por Paquete", value=contenido_paquete if contenido_paquete > 1 else 10.0, min_value=1.0)
                    factor_final = cant_paq
                    unidad_final = f"Paquete x{int(cant_paq)}"
                else:
                    factor_final = 1.0
                    unidad_final = "Unidad Suelta"
            elif tipo_sel == "Peso (Kg/Lb)":
                unidad_peso = col_u1.selectbox("Presentación", ["Kilo (1000g)", "Libra (500g)", "Bulto (50kg)", "Bulto (25kg)", "Gramo"])
                if "Kilo" in unidad_peso: factor_final = 1000.0
                elif "Libra" in unidad_peso: factor_final = 500.0
                elif "50kg" in unidad_peso: factor_final = 50000.0
                elif "25kg" in unidad_peso: factor_final = 25000.0
                elif "Gramo" in unidad_peso: factor_final = 1.0
                unidad_final = unidad_peso
            elif tipo_sel == "Volumen (Lt/Ml)":
                unidad_vol = col_u1.selectbox("Presentación", ["Litro (1000ml)", "Galón (3785ml)", "Botella (750ml)", "Mililitro"])
                if "Litro" in unidad_vol: factor_final = 1000.0
                elif "Galón" in unidad_vol: factor_final = 3785.0
                elif "Botella" in unidad_vol: factor_final = 750.0
                elif "Mililitro" in unidad_vol: factor_final = 1.0
                unidad_final = unidad_vol

            st.write("💰 **Inventario y Costos**")
            c4, c5, c6, c7 = st.columns(4)
            
            label_stock = f"Stock ({'Paq' if factor_final > 1 else 'Und/Kg'})"
            new_stock_visual = c4.number_input(label_stock, value=stock_actual, min_value=0.0)
            new_minimo_visual = c5.number_input("Stock Mínimo", value=stock_minimo, min_value=0.0)
            new_costo_ref = c6.number_input("Costo Ref ($)", value=costo_referencia, step=500.0)
            new_merma = c7.number_input("% Merma", value=merma, min_value=0.0, max_value=99.0)

            # Cálculos Backend
            stock_real_db = new_stock_visual * factor_final
            min_real_db = new_minimo_visual * factor_final
            
            costo_unit_estimado = new_costo_ref / factor_final if factor_final > 0 else 0
            if new_merma > 0:
                costo_unit_estimado = costo_unit_estimado / (1 - (new_merma/100))

            st.write("")
            if st.button("💾 GUARDAR CAMBIOS", type="primary", use_container_width=True):
                if new_nombre:
                    try:
                        # Guardamos el mejor proveedor calculado automáticamente
                        fila_datos = [
                            id_ins, new_nombre, new_cat, unidad_final, 
                            factor_final, new_costo_ref, stock_real_db, min_real_db, 
                            costo_unit_estimado, new_merma, mejor_proveedor_calc
                        ]
                        
                        if modo == "Crear Nuevo":
                            ws.append_row(fila_datos)
                            st.success(f"✅ {new_nombre} Creado.")
                        else:
                            cell = ws.find(id_ins)
                            ws.update(f"A{cell.row}:K{cell.row}", [fila_datos])
                            st.success(f"✅ {new_nombre} Actualizado.")
                        
                        limpiar_cache()
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error guardando: {e}")
                else:
                    st.warning("Nombre obligatorio.")

    # --- TAB 2: VISOR ---
    with tab2:
        st.subheader("📊 Base de Datos de Insumos")
        
        if st.button("🛠️ REPARAR ENCABEZADOS DB (Clic si hay error)"):
            if reparar_encabezados(sheet):
                st.success("✅ DB Organizada.")
                time.sleep(1); st.rerun()
        
        if not df.empty and "Nombre_Insumo" in df.columns:
            # Mostrar la columna automática Proveedor_Sugerido
            cols_ver = ["Nombre_Insumo", "Categoria", "Unidad_Compra", "Stock_Actual_Gr"]
            if "Proveedor_Sugerido" in df.columns: cols_ver.append("Proveedor_Sugerido")
            
            st.dataframe(df[[c for c in cols_ver if c in df.columns]], use_container_width=True, hide_index=True)
        else:
            st.info("Sin datos.")

    # --- TAB 3: TENDENCIAS ---
    with tab3:
        st.subheader("📈 Evolución de Precios")
        if not df_compras.empty and "Nombre_Insumo" in df_compras.columns:
            insumo_sel = st.selectbox("Ver tendencia:", sorted(df["Nombre_Insumo"].unique()))
            if insumo_sel:
                hist = df_compras[df_compras["Nombre_Insumo"] == insumo_sel].copy()
                if not hist.empty:
                    hist["Fecha"] = pd.to_datetime(hist["Fecha_Registro"])
                    hist["Total"] = pd.to_numeric(hist["Precio_Total_Pagado"], errors='coerce')
                    hist["Cant"] = pd.to_numeric(hist["Cantidad_Compra_Original"], errors='coerce')
                    hist["Costo_Unit"] = hist["Total"] / hist["Cant"]
                    hist = hist.sort_values("Fecha")
                    
                    fig = px.line(hist, x="Fecha", y="Costo_Unit", color="Proveedor", markers=True)
                    st.plotly_chart(fig, use_container_width=True)
                else: st.warning("Sin historial.")
        else: st.info("Registra compras primero.")