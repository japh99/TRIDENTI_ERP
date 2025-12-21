import streamlit as st
import pandas as pd
import urllib.parse
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
        df = leer_datos_seguro(ws)
    except:
        st.error("No se pudo leer la base de insumos.")
        return

    # VALIDACIÓN: Si la hoja está vacía o no tiene la columna principal
    if df.empty or "Stock_Actual_Gr" not in df.columns:
        st.success("🎉 **Inventario Limpio:** No hay insumos registrados para procesar sugeridos.")
        return

    # 2. PROCESAMIENTO NUMÉRICO
    columnas_numericas = ["Stock_Actual_Gr", "Stock_Minimo_Gr", "Factor_Conversion_Gr", "Costo_Ultima_Compra"]
    for col in columnas_numericas:
        if col in df.columns:
            df[col] = df[col].apply(limpiar_numero)
        else:
            df[col] = 0.0

    df["Costo_Unitario"] = df["Costo_Ultima_Compra"]
    
    # LÓGICA DE VISUALIZACIÓN
    def explicar_stock(row):
        actual = row["Stock_Actual_Gr"]
        factor = row["Factor_Conversion_Gr"]
        unidad = str(row.get("Unidad_Compra", "Unidad"))
        if factor <= 0: factor = 1
        compra = actual / factor
        
        if "Kilo" in unidad or "Libra" in unidad:
            return f"{compra:.2f} {unidad} (= {actual:,.0f} g)"
        elif "Litro" in unidad or "Botella" in unidad:
            return f"{compra:.2f} {unidad} (= {actual:,.0f} ml)"
        elif factor > 1:
            return f"{compra:.1f} {unidad} (= {actual:,.0f} unds)"
        else:
            return f"{actual:,.0f} Unidades"

    df["Stock_Explicado"] = df.apply(explicar_stock, axis=1)

    # Semáforo de Alertas
    def evaluar_stock(row):
        act = row["Stock_Actual_Gr"]
        mini = row["Stock_Minimo_Gr"]
        if mini == 0: return "⚪ Sin Configurar"
        if act <= 0: return "🔴 AGOTADO"
        if act <= mini: return "🔴 CRÍTICO"
        if act <= (mini * 1.2): return "🟡 ALERTA"
        return "🟢 OK"

    df["Estado"] = df.apply(evaluar_stock, axis=1)
    
    # 3. FILTRAR PEDIDOS
    df_pedidos = df[df["Estado"].isin(["🔴 AGOTADO", "🔴 CRÍTICO", "🟡 ALERTA"])].copy()
    
    if not df_pedidos.empty:
        df_pedidos["Cantidad_A_Pedir"] = (
            ((df_pedidos["Stock_Minimo_Gr"] * 2) - df_pedidos["Stock_Actual_Gr"]) / 
            df_pedidos["Factor_Conversion_Gr"].replace(0, 1)
        ).clip(lower=0).apply(lambda x: round(x, 1))

        st.subheader("⚠️ Insumos que requieren atención")
        
        df_final = st.data_editor(
            df_pedidos[["Nombre_Insumo", "Estado", "Stock_Explicado", "Costo_Unitario", "Cantidad_A_Pedir"]],
            column_config={
                "Nombre_Insumo": st.column_config.TextColumn("Insumo", disabled=True),
                "Estado": st.column_config.TextColumn("Alerta", disabled=True),
                "Stock_Explicado": st.column_config.TextColumn("Stock Actual", disabled=True),
                "Costo_Unitario": st.column_config.NumberColumn("Costo Unit.", format="$%d", disabled=True),
                "Cantidad_A_Pedir": st.column_config.NumberColumn("🛒 A COMPRAR", required=True, min_value=0.0, step=0.5)
            },
            hide_index=True,
            use_container_width=True,
            key="editor_sugerido_v3"
        )
        
        total_est = (df_final["Cantidad_A_Pedir"] * df_final["Costo_Unitario"]).sum()
        st.metric("💰 Presupuesto Estimado", formato_moneda(total_est))
        
        # WhatsApp
        cel = st.text_input("Enviar a (WhatsApp):", value="57")
        if st.button("📲 GENERAR Y ENVIAR PEDIDO"):
            txt = f"*REQUISICIÓN - {pd.Timestamp.now().strftime('%Y-%m-%d')}*\n\n"
            items = 0
            for _, r in df_final.iterrows():
                if r["Cantidad_A_Pedir"] > 0:
                    uni = df[df["Nombre_Insumo"] == r["Nombre_Insumo"]].iloc[0]["Unidad_Compra"]
                    txt += f"📦 {r['Cantidad_A_Pedir']} {uni} - *{r['Nombre_Insumo']}*\n"
                    items += 1
            if items > 0:
                txt += f"\n*Valor Aprox:* {formato_moneda(total_est)}\n"
                link = f"https://wa.me/{cel}?text={urllib.parse.quote(txt)}"
                st.markdown(f'<a href="{link}" target="_blank">Click aquí para abrir WhatsApp</a>', unsafe_allow_html=True)
            else:
                st.warning("No hay productos para pedir.")
    else:
        st.success("🎉 Inventario saludable. No hay sugeridos de compra.")

    st.markdown("---")
    with st.expander("🔍 Ver Inventario Completo"):
        st.dataframe(df[["Nombre_Insumo", "Estado", "Stock_Explicado", "Stock_Minimo_Gr"]], use_container_width=True, hide_index=True)
