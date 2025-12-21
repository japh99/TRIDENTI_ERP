import streamlit as st
import pandas as pd
import urllib.parse
# Agregamos leer_datos_seguro a los imports
from utils import conectar_google_sheets, leer_datos_seguro

# --- CONFIGURACIÓN ---
HOJA_INSUMOS = "DB_INSUMOS"

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return str(valor)

def limpiar_numero(valor):
    if pd.isna(valor) or valor == "" or valor is None: return 0.0
    try: 
        # Maneja tanto comas como puntos decimales
        s = str(valor).replace(",", ".")
        return float(s)
    except: 
        return 0.0

def show(sheet):
    st.title("🛒 Sugerido de Compras & Presupuesto")
    st.caption("Planifica tu reabastecimiento con claridad.")
    st.markdown("---")
    
    if not sheet: return

    # 1. CARGAR DATOS DE FORMA SEGURA
    try:
        ws = sheet.worksheet(HOJA_INSUMOS)
        # Usamos leer_datos_seguro para que si está vacía no rompa el código
        df = leer_datos_seguro(ws)
    except:
        st.error("No se pudo leer la base de insumos.")
        return

    # --- VALIDACIÓN CRÍTICA PARA EVITAR KEYERROR ---
    if df.empty or "Stock_Actual_Gr" not in df.columns:
        st.success("🎉 **Inventario Limpio:** No hay insumos registrados para procesar sugeridos.")
        return

    # 2. PROCESAMIENTO NUMÉRICO (Ahora es seguro porque validamos arriba)
    columnas_numericas = ["Stock_Actual_Gr", "Stock_Minimo_Gr", "Factor_Conversion_Gr", "Costo_Ultima_Compra"]
    for col in columnas_numericas:
        if col in df.columns:
            df[col] = df[col].apply(limpiar_numero)
        else:
            df[col] = 0.0

    df["Costo_Unitario"] = df["Costo_Ultima_Compra"]
    
    # --- LÓGICA DE VISUALIZACIÓN ---
    def explicar_stock(row):
        total_interno = row["Stock_Actual_Gr"]
        factor = row["Factor_Conversion_Gr"]
        unidad_compra = str(row.get("Unidad_Compra", "Unidad"))
        
        if factor <= 0: factor = 1
        cantidad_compra = total_interno / factor
        
        if "Kilo" in unidad_compra or "Libra" in unidad_compra:
            return f"{cantidad_compra:.2f} {unidad_compra} (= {total_interno:,.0f} g)"
        elif "Litro" in unidad_compra or "Botella" in unidad_compra:
            return f"{cantidad_compra:.2f} {unidad_compra} (= {total_interno:,.0f} ml)"
        elif factor > 1:
            return f"{cantidad_compra:.1f} {unidad_compra} (= {total_interno:,.0f} unds)"
        else:
            return f"{total_interno:,.0f} Unidades"

    df["Stock_Explicado"] = df.apply(explicar_stock, axis=1)

    # Semáforo
    def evaluar_stock(row):
        actual = row["Stock_Actual_Gr"]
        minimo = row["Stock_Minimo_Gr"]
        if minimo == 0: return "⚪ Sin Configurar"
        if actual <= 0: return "🔴 AGOTADO"
        if actual <= minimo: return "🔴 CRÍTICO"
        if actual <= (minimo * 1.2): return "🟡 ALERTA"
        return "🟢 OK"

    df["Estado"] = df.apply(evaluar_stock, axis=1)
    
    # 3. FILTRAR PEDIDOS
    df_pedidos = df[df["Estado"].isin(["🔴 AGOTADO", "🔴 CRÍTICO", "🟡 ALERTA"])].copy()
    
    if not df_pedidos.empty:
        # Sugerido en unidades de compra
        df_pedidos["Cantidad_A_Pedir"] = (
            ((df_pedidos["Stock_Minimo_Gr"] * 2) - df_pedidos["Stock_Actual_Gr"]) / 
            df_pedidos["Factor_Conversion_Gr"].replace(0, 1)
        ).clip(lower=0).apply(lambda x: round(x, 1))

        st.subheader("⚠️ Insumos que requieren atención")
        st.info("👇 Revisa la columna **'Stock Actual'** para ver el desglose.")
        
        df_editor = df_pedidos[[
            "Nombre_Insumo", 
            "Estado", 
            "Stock_Explicado", 
            "Costo_Unitario", 
            "Cantidad_A_Pedir"
        ]]
        
        df_final = st.data_editor(
            df_editor,
            column_config={
                "Nombre_Insumo": st.column_config.TextColumn("Insumo", disabled=True),
                "Estado": st.column_config.TextColumn("Alerta", disabled=True),
                "Stock_Explicado": st.column_config.TextColumn("Stock Actual", disabled=True),
                "Costo_Unitario": st.column_config.NumberColumn("Costo Unit.", format="$%d", disabled=True),
                "Cantidad_A_Pedir": st.column_config.NumberColumn("🛒 A COMPRAR", required=True, min_value=0.0, step=0.5)
            },
            hide_index=True,
            use_container_width=True,
            key="editor_sugerido_v2"
        )
        
        # Presupuesto y WhatsApp (Misma lógica que tenías)
        total_estimado = (df_final["Cantidad_A_Pedir"] * df_final["Costo_Unitario"]).sum()
        st.metric("💰 Presupuesto Estimado", formato_moneda(total_estimado))
        
        # --- WHATSAPP ---
        celular = st.text_input("Enviar a (WhatsApp):", value="57")
        if st.button("📲 GENERAR Y ENVIAR PEDIDO"):
            texto_pedido = f"*REQUISICIÓN - {pd.Timestamp.now().strftime('%Y-%m-%d')}*\n\n"
            items = 0
            for _, row in df_final.iterrows():
                if row["Cantidad_A_Pedir"] > 0:
                    unidad = df[df["Nombre_Insumo"] == row["Nombre_Insumo"]].iloc[0]["Unidad_Compra"]
                    texto_pedido += f"📦 {row['Cantidad_A_Pedir']} {unidad} - *{row['Nombre_Insumo']}*\n"
                    items += 1
            
            if items > 0:
                texto_pedido += f"\n*Valor Aprox:* {formato_moneda(total_estimado)}\n"
                link = f"https://wa.me/{celular}?text={urllib.parse.quote(texto_pedido)}"
                st.markdown(f'<a href="{link}" target="_blank">Click aquí para abrir WhatsApp</a>', unsafe_allow_html=True)
            else:
                st.warning("No hay productos con cantidad mayor a 0.")
    else:
        st.success("🎉 Inventario saludable. No hay sugeridos de compra por ahora.")

    st.markdown("---")
    with st.expander("🔍 Ver Inventario Completo"):
        st.dataframe(df[["Nombre_Insumo", "Estado", "Stock_Explicado", "Stock_Minimo_Gr"]], use_container_width=True)import streamlit as st
import pandas as pd
import urllib.parse
# Agregamos leer_datos_seguro a los imports
from utils import conectar_google_sheets, leer_datos_seguro

# --- CONFIGURACIÓN ---
HOJA_INSUMOS = "DB_INSUMOS"

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return str(valor)

def limpiar_numero(valor):
    if pd.isna(valor) or valor == "" or valor is None: return 0.0
    try: 
        # Maneja tanto comas como puntos decimales
        s = str(valor).replace(",", ".")
        return float(s)
    except: 
        return 0.0

def show(sheet):
    st.title("🛒 Sugerido de Compras & Presupuesto")
    st.caption("Planifica tu reabastecimiento con claridad.")
    st.markdown("---")
    
    if not sheet: return

    # 1. CARGAR DATOS DE FORMA SEGURA
    try:
        ws = sheet.worksheet(HOJA_INSUMOS)
        # Usamos leer_datos_seguro para que si está vacía no rompa el código
        df = leer_datos_seguro(ws)
    except:
        st.error("No se pudo leer la base de insumos.")
        return

    # --- VALIDACIÓN CRÍTICA PARA EVITAR KEYERROR ---
    if df.empty or "Stock_Actual_Gr" not in df.columns:
        st.success("🎉 **Inventario Limpio:** No hay insumos registrados para procesar sugeridos.")
        return

    # 2. PROCESAMIENTO NUMÉRICO (Ahora es seguro porque validamos arriba)
    columnas_numericas = ["Stock_Actual_Gr", "Stock_Minimo_Gr", "Factor_Conversion_Gr", "Costo_Ultima_Compra"]
    for col in columnas_numericas:
        if col in df.columns:
            df[col] = df[col].apply(limpiar_numero)
        else:
            df[col] = 0.0

    df["Costo_Unitario"] = df["Costo_Ultima_Compra"]
    
    # --- LÓGICA DE VISUALIZACIÓN ---
    def explicar_stock(row):
        total_interno = row["Stock_Actual_Gr"]
        factor = row["Factor_Conversion_Gr"]
        unidad_compra = str(row.get("Unidad_Compra", "Unidad"))
        
        if factor <= 0: factor = 1
        cantidad_compra = total_interno / factor
        
        if "Kilo" in unidad_compra or "Libra" in unidad_compra:
            return f"{cantidad_compra:.2f} {unidad_compra} (= {total_interno:,.0f} g)"
        elif "Litro" in unidad_compra or "Botella" in unidad_compra:
            return f"{cantidad_compra:.2f} {unidad_compra} (= {total_interno:,.0f} ml)"
        elif factor > 1:
            return f"{cantidad_compra:.1f} {unidad_compra} (= {total_interno:,.0f} unds)"
        else:
            return f"{total_interno:,.0f} Unidades"

    df["Stock_Explicado"] = df.apply(explicar_stock, axis=1)

    # Semáforo
    def evaluar_stock(row):
        actual = row["Stock_Actual_Gr"]
        minimo = row["Stock_Minimo_Gr"]
        if minimo == 0: return "⚪ Sin Configurar"
        if actual <= 0: return "🔴 AGOTADO"
        if actual <= minimo: return "🔴 CRÍTICO"
        if actual <= (minimo * 1.2): return "🟡 ALERTA"
        return "🟢 OK"

    df["Estado"] = df.apply(evaluar_stock, axis=1)
    
    # 3. FILTRAR PEDIDOS
    df_pedidos = df[df["Estado"].isin(["🔴 AGOTADO", "🔴 CRÍTICO", "🟡 ALERTA"])].copy()
    
    if not df_pedidos.empty:
        # Sugerido en unidades de compra
        df_pedidos["Cantidad_A_Pedir"] = (
            ((df_pedidos["Stock_Minimo_Gr"] * 2) - df_pedidos["Stock_Actual_Gr"]) / 
            df_pedidos["Factor_Conversion_Gr"].replace(0, 1)
        ).clip(lower=0).apply(lambda x: round(x, 1))

        st.subheader("⚠️ Insumos que requieren atención")
        st.info("👇 Revisa la columna **'Stock Actual'** para ver el desglose.")
        
        df_editor = df_pedidos[[
            "Nombre_Insumo", 
            "Estado", 
            "Stock_Explicado", 
            "Costo_Unitario", 
            "Cantidad_A_Pedir"
        ]]
        
        df_final = st.data_editor(
            df_editor,
            column_config={
                "Nombre_Insumo": st.column_config.TextColumn("Insumo", disabled=True),
                "Estado": st.column_config.TextColumn("Alerta", disabled=True),
                "Stock_Explicado": st.column_config.TextColumn("Stock Actual", disabled=True),
                "Costo_Unitario": st.column_config.NumberColumn("Costo Unit.", format="$%d", disabled=True),
                "Cantidad_A_Pedir": st.column_config.NumberColumn("🛒 A COMPRAR", required=True, min_value=0.0, step=0.5)
            },
            hide_index=True,
            use_container_width=True,
            key="editor_sugerido_v2"
        )
        
        # Presupuesto y WhatsApp (Misma lógica que tenías)
        total_estimado = (df_final["Cantidad_A_Pedir"] * df_final["Costo_Unitario"]).sum()
        st.metric("💰 Presupuesto Estimado", formato_moneda(total_estimado))
        
        # --- WHATSAPP ---
        celular = st.text_input("Enviar a (WhatsApp):", value="57")
        if st.button("📲 GENERAR Y ENVIAR PEDIDO"):
            texto_pedido = f"*REQUISICIÓN - {pd.Timestamp.now().strftime('%Y-%m-%d')}*\n\n"
            items = 0
            for _, row in df_final.iterrows():
                if row["Cantidad_A_Pedir"] > 0:
                    unidad = df[df["Nombre_Insumo"] == row["Nombre_Insumo"]].iloc[0]["Unidad_Compra"]
                    texto_pedido += f"📦 {row['Cantidad_A_Pedir']} {unidad} - *{row['Nombre_Insumo']}*\n"
                    items += 1
            
            if items > 0:
                texto_pedido += f"\n*Valor Aprox:* {formato_moneda(total_estimado)}\n"
                link = f"https://wa.me/{celular}?text={urllib.parse.quote(texto_pedido)}"
                st.markdown(f'<a href="{link}" target="_blank">Click aquí para abrir WhatsApp</a>', unsafe_allow_html=True)
            else:
                st.warning("No hay productos con cantidad mayor a 0.")
    else:
        st.success("🎉 Inventario saludable. No hay sugeridos de compra por ahora.")

    st.markdown("---")
    with st.expander("🔍 Ver Inventario Completo"):
        st.dataframe(df[["Nombre_Insumo", "Estado", "Stock_Explicado", "Stock_Minimo_Gr"]], use_container_width=True)
