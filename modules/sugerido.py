import streamlit as st
import pandas as pd
import urllib.parse
from utils import conectar_google_sheets

# --- CONFIGURACIÓN ---
HOJA_INSUMOS = "DB_INSUMOS"

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return str(valor)

def limpiar_numero(valor):
    try: return float(str(valor).replace(",", "."))
    except: return 0.0

def show(sheet):
    st.title("🛒 Sugerido de Compras & Presupuesto")
    st.caption("Planifica tu reabastecimiento con claridad.")
    st.markdown("---")
    
    if not sheet: return

    # 1. CARGAR DATOS
    try:
        ws = sheet.worksheet(HOJA_INSUMOS)
        df = pd.DataFrame(ws.get_all_records())
    except:
        st.error("No se pudo leer la base de insumos.")
        return

    # 2. PROCESAMIENTO NUMÉRICO
    df["Stock_Actual_Gr"] = df["Stock_Actual_Gr"].apply(limpiar_numero)
    df["Stock_Minimo_Gr"] = df["Stock_Minimo_Gr"].apply(limpiar_numero)
    df["Factor_Conversion_Gr"] = df["Factor_Conversion_Gr"].apply(limpiar_numero)
    df["Costo_Unitario"] = df["Costo_Ultima_Compra"].apply(limpiar_numero)
    
    # --- LA NUEVA LÓGICA DE VISUALIZACIÓN DETALLADA ---
    def explicar_stock(row):
        total_interno = row["Stock_Actual_Gr"] # Lo que hay en base de datos (g, ml, und)
        factor = row["Factor_Conversion_Gr"]
        unidad_compra = str(row["Unidad_Compra"])
        
        if factor <= 0: factor = 1
        
        cantidad_compra = total_interno / factor
        
        # CASO A: PESO (Gramos -> Kilos/Libras)
        if "Kilo" in unidad_compra or "Libra" in unidad_compra or "Bulto" in unidad_compra:
            # Ej: 2.5 Kilos (= 2500 g)
            return f"{cantidad_compra:.2f} {unidad_compra} (= {total_interno:,.0f} g)"
            
        # CASO B: VOLUMEN (Mililitros -> Litros/Botellas)
        elif "Litro" in unidad_compra or "Galón" in unidad_compra or "Botella" in unidad_compra:
            # Ej: 1.5 Litros (= 1500 ml)
            return f"{cantidad_compra:.2f} {unidad_compra} (= {total_interno:,.0f} ml)"
            
        # CASO C: PAQUETES (Unidades agrupadas)
        elif factor > 1:
            # Ej: 4.3 Paquete x10 (= 43 unds)
            return f"{cantidad_compra:.1f} {unidad_compra} (= {total_interno:,.0f} unds)"
            
        # CASO D: UNITARIO (Factor 1)
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
    
    # 3. FILTRAR
    df_pedidos = df[df["Estado"].isin(["🔴 AGOTADO", "🔴 CRÍTICO", "🟡 ALERTA"])].copy()
    
    # Sugerido en unidades de compra
    df_pedidos["Cantidad_A_Pedir"] = (
        ((df_pedidos["Stock_Minimo_Gr"] * 2) - df_pedidos["Stock_Actual_Gr"]) / 
        df_pedidos["Factor_Conversion_Gr"].replace(0, 1)
    ).clip(lower=0)
    
    df_pedidos["Cantidad_A_Pedir"] = df_pedidos["Cantidad_A_Pedir"].apply(lambda x: round(x, 1))

    st.subheader("⚠️ Insumos que requieren atención")
    
    if not df_pedidos.empty:
        st.info("👇 Revisa la columna **'Stock Actual'** para ver el desglose.")
        
        df_editor = df_pedidos[[
            "Nombre_Insumo", 
            "Estado", 
            "Stock_Explicado", # Usamos la nueva columna detallada
            "Costo_Unitario", 
            "Cantidad_A_Pedir"
        ]]
        
        df_final = st.data_editor(
            df_editor,
            column_config={
                "Nombre_Insumo": st.column_config.TextColumn("Insumo", disabled=True),
                "Estado": st.column_config.TextColumn("Alerta", disabled=True, width="small"),
                "Stock_Explicado": st.column_config.TextColumn("Stock Actual (Detalle)", disabled=True, width="large"),
                "Costo_Unitario": st.column_config.NumberColumn("Costo Unit.", format="$%d", disabled=True),
                "Cantidad_A_Pedir": st.column_config.NumberColumn("🛒 A COMPRAR", required=True, min_value=0.0, step=0.5)
            },
            hide_index=True,
            use_container_width=True,
            key="editor_sugerido"
        )
        
        # Presupuesto
        total_estimado = (df_final["Cantidad_A_Pedir"] * df_final["Costo_Unitario"]).sum()
        
        st.markdown("---")
        c1, c2 = st.columns([2, 1])
        c1.metric("💰 Presupuesto Estimado", formato_moneda(total_estimado))
        
        # Enviar
        st.write("### 📤 Enviar Pedido")
        col_dest, col_btn = st.columns([1, 1])
        with col_dest:
            celular = st.text_input("Enviar a (WhatsApp):", value="57", placeholder="Ej: 573001234567")
            
        fecha_hoy = pd.Timestamp.now().strftime("%Y-%m-%d")
        texto_pedido = f"*REQUISICIÓN DE COMPRA - {fecha_hoy}* 📋\n\n"
        items_pedir = 0
        
        # Necesitamos recuperar la Unidad de Compra original para el mensaje
        # Hacemos un cruce simple
        for index, row in df_final.iterrows():
            cant = row["Cantidad_A_Pedir"]
            if cant > 0:
                # Buscamos la unidad original en el DF principal
                nombre_ins = row["Nombre_Insumo"]
                unidad = df[df["Nombre_Insumo"] == nombre_ins].iloc[0]["Unidad_Compra"]
                
                texto_pedido += f"📦 {cant} {unidad} - *{nombre_ins}*\n"
                items_pedir += 1
        
        texto_pedido += f"\n💰 *Valor Aprox:* {formato_moneda(total_estimado)}\n"
        texto_pedido += "\nAtt: Sistema Tridenti ERP 🔱"
        
        texto_encoded = urllib.parse.quote(texto_pedido)
        
        with col_btn:
            st.write("") 
            st.write("") 
            if items_pedir > 0:
                if celular.strip() and celular != "57":
                    link_whatsapp = f"https://wa.me/{celular.strip()}?text={texto_encoded}"
                    label_btn = f"📲 ENVIAR REPORTE AHORA"
                else:
                    link_whatsapp = f"https://wa.me/?text={texto_encoded}"
                    label_btn = "📲 SELECCIONAR CONTACTO"
                
                st.link_button(label_btn, link_whatsapp, type="primary", use_container_width=True)
            else:
                st.warning("Cantidades en 0.")

    else:
        st.success("🎉 Inventario saludable.")
        
    st.markdown("---")
    with st.expander("🔍 Ver Inventario Completo"):
        # Mostramos la columna explicada también aquí
        if "Stock_Explicado" in df.columns:
            st.dataframe(df[["Nombre_Insumo", "Estado", "Stock_Explicado", "Stock_Minimo_Gr"]], use_container_width=True)