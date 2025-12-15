import streamlit as st
import pandas as pd
import plotly.express as px
from utils import leer_datos_seguro, limpiar_numero

def show(sheet):
    st.header("🧠 Monitor de Precios (Histórico y Comparativo)")
    
    try:
        hoja_log = sheet.worksheet("LOG_COMPRAS")
        df_log = leer_datos_seguro(hoja_log)
        if not df_log.empty: df_log.columns = df_log.columns.str.strip()
    except: return

    if not df_log.empty and 'Nombre_Insumo' in df_log.columns:
        lista = sorted(df_log['Nombre_Insumo'].unique().tolist())
        insumo = st.selectbox("📦 Producto:", lista)
        
        if insumo:
            # 1. PREPARAR DATOS
            df = df_log[df_log['Nombre_Insumo'] == insumo].copy()
            df['Fecha'] = pd.to_datetime(df['Fecha_Registro'])
            df = df.sort_values('Fecha')
            
            # Limpiar números
            df['Pago_Total'] = df['Precio_Total_Pagado'].apply(limpiar_numero)
            df['Cant_Manual'] = df['Cantidad_Compra_Original'].apply(limpiar_numero)
            df = df[df['Cant_Manual'] > 0]
            
            # Precio Base
            df['Precio_Base'] = df['Pago_Total'] / df['Cant_Manual']
            
            # --- INTELIGENCIA DE ESCALA (Para que se vea en miles) ---
            promedio = df['Precio_Base'].mean()
            multiplicador = 1
            etiqueta = "Unidad Comprada"
            
            if promedio < 100: 
                multiplicador = 1000
                etiqueta = "KILO / LITRO (Proyección x1000)"
            
            df['Precio_Grafica'] = df['Precio_Base'] * multiplicador
            
            # ---------------------------------------------------------
            # GRÁFICO 1: LÍNEA DE TIEMPO (LO QUE TÚ QUIERES)
            # ---------------------------------------------------------
            st.write(f"### 📉 Evolución en el Tiempo ({etiqueta})")
            st.info("Aquí puedes ver si el precio ha subido o bajado mes a mes.")
            
            fig_linea = px.line(
                df, 
                x='Fecha', 
                y='Precio_Grafica', 
                color='Proveedor', 
                markers=True,
                text='Precio_Grafica',
                title=f"Tendencia de Precios: {insumo}"
            )
            fig_linea.update_traces(textposition="bottom right", texttemplate='$%{text:,.0f}')
            fig_linea.update_layout(yaxis_title="Precio", xaxis_title="Fecha de Compra")
            st.plotly_chart(fig_linea, use_container_width=True)

            st.markdown("---")

            # ---------------------------------------------------------
            # GRÁFICO 2: COMPARATIVA ACTUAL (QUIÉN GANA HOY)
            # ---------------------------------------------------------
            st.write(f"### ⚖️ Comparativa Última Compra")
            
            # Tomamos solo la última fecha de cada proveedor
            df_final = df.sort_values('Fecha').groupby('Proveedor').tail(1).reset_index()
            df_final = df_final.sort_values('Precio_Grafica')
            
            if not df_final.empty:
                mejor = df_final.iloc[0]
                st.success(f"🏆 GANADOR ACTUAL: **{mejor['Proveedor']}** a **${mejor['Precio_Grafica']:,.0f}**")
                
                fig_bar = px.bar(df_final, x='Proveedor', y='Precio_Grafica', 
                           color='Precio_Grafica', color_continuous_scale='RdYlGn_r', 
                           text_auto='$,.0f')
                st.plotly_chart(fig_bar, use_container_width=True)
                
                with st.expander("Ver Tabla de Datos Completa"):
                    st.dataframe(df[['Fecha_Registro', 'Proveedor', 'Cant_Manual', 'Unidad_Original', 'Pago_Total', 'Precio_Grafica']].sort_values('Fecha_Registro', ascending=False))
            else:
                st.warning("Sin datos válidos.")