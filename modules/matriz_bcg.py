import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from utils import conectar_google_sheets, leer_datos_seguro, limpiar_numero

# --- CONFIGURACIÓN ---
HOJA_VENTAS = "LOG_VENTAS_LOYVERSE"
HOJA_RECETAS = "DB_RECETAS"
HOJA_INSUMOS = "DB_INSUMOS"

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

# --- BACKEND ---
@st.cache_data(ttl=300)
def cargar_datos_bcg(_sheet):
    """Carga y cruza Ventas, Recetas e Insumos."""
    try:
        ws_v = _sheet.worksheet(HOJA_VENTAS)
        ws_r = _sheet.worksheet(HOJA_RECETAS)
        ws_i = _sheet.worksheet(HOJA_INSUMOS)
        
        data_v = ws_v.get_all_records()
        data_r = ws_r.get_all_values()
        data_i = ws_i.get_all_records()

        # Ventas
        df_v = pd.DataFrame(data_v)
        if not df_v.empty:
            df_v["Fecha"] = pd.to_datetime(df_v["Fecha"])
            df_v["Total_Dinero"] = pd.to_numeric(df_v["Total_Dinero"], errors='coerce').fillna(0)
            df_v["Cantidad_Vendida"] = pd.to_numeric(df_v["Cantidad_Vendida"], errors='coerce').fillna(0)

        # Insumos
        df_i = pd.DataFrame(data_i)
        if not df_i.empty:
            df_i["Costo_Promedio_Ponderado"] = df_i["Costo_Promedio_Ponderado"].apply(limpiar_numero)
            mapa_costos = dict(zip(df_i["Nombre_Insumo"], df_i["Costo_Promedio_Ponderado"]))
        else: mapa_costos = {}

        # Recetas
        if len(data_r) > 1:
            df_r = pd.DataFrame(data_r[1:], columns=data_r[0])
            if len(df_r.columns) >= 5:
                df_r = df_r.iloc[:, [1, 3, 4]]
                df_r.columns = ["Nombre_Plato", "Ingrediente", "Cantidad"]
            else: df_r = pd.DataFrame(columns=["Nombre_Plato", "Ingrediente", "Cantidad"])
        else: df_r = pd.DataFrame(columns=["Nombre_Plato", "Ingrediente", "Cantidad"])

        costos_platos = {}
        if not df_r.empty:
            for plato in df_r["Nombre_Plato"].unique():
                ings = df_r[df_r["Nombre_Plato"] == plato]
                costo = 0
                for _, row in ings.iterrows():
                    insumo = row["Ingrediente"]
                    try: cant = float(str(row["Cantidad"]).replace(",", "."))
                    except: cant = 0
                    costo += mapa_costos.get(insumo, 0) * cant
                costos_platos[plato] = costo

        return df_v, costos_platos
    except: return pd.DataFrame(), {}

def show(sheet):
    st.title("🚀 Matriz BCG (Ingeniería de Menú)")
    
    # --- AYUDA VISUAL EXPANDIBLE ---
    with st.expander("📘 ¿CÓMO LEER ESTA MATRIZ? (Guía Gerencial)", expanded=False):
        st.markdown("""
        Esta herramienta clasifica tus platos cruzando dos variables: **¿Cuánto se vende?** (Popularidad) vs **¿Cuánto dinero deja?** (Rentabilidad).
        
        *   ⭐ **ESTRELLA (Alto/Alto):** Los reyes de la carta. La gente los ama y tú ganas dinero.
        *   🐄 **VACA LECHERA (Alto/Bajo):** Se venden solos, pero dejan poco margen. Son el flujo de caja diario.
        *   🧩 **INCÓGNITA (Bajo/Alto):** Dejan mucha ganancia, pero nadie los pide. ¡Son un tesoro escondido!
        *   🐕 **HUESO (Bajo/Bajo):** Ni se venden, ni dan plata. Solo estorban en la nevera.
        """)
    
    st.markdown("---")
    
    if not sheet: return

    # 1. CARGA
    with st.spinner("Analizando rentabilidad..."):
        df_ventas, dict_costos = cargar_datos_bcg(sheet)

    if df_ventas.empty:
        st.warning("No hay ventas registradas.")
        return

    # 2. FILTRO
    col_date, col_kpi = st.columns([1, 2])
    with col_date:
        min_d = df_ventas["Fecha"].min().date()
        max_d = df_ventas["Fecha"].max().date()
        rango = st.date_input("Periodo:", [min_d, max_d])
    
    if len(rango) != 2: st.stop()

    df_periodo = df_ventas[(df_ventas["Fecha"].dt.date >= rango[0]) & (df_ventas["Fecha"].dt.date <= rango[1])]
    
    if df_periodo.empty:
        st.warning("No hay ventas en este periodo.")
        st.stop()

    # 3. CÁLCULOS
    df_bcg = df_periodo.groupby("Nombre_Plato").agg(Unidades=('Cantidad_Vendida', 'sum'), Venta_Total=('Total_Dinero', 'sum')).reset_index()

    df_bcg["Costo_Unitario"] = df_bcg["Nombre_Plato"].map(dict_costos).fillna(0)
    df_bcg["Precio_Promedio"] = df_bcg.apply(lambda x: x["Venta_Total"] / x["Unidades"] if x["Unidades"] > 0 else 0, axis=1)
    df_bcg["Margen_Unitario"] = df_bcg["Precio_Promedio"] - df_bcg["Costo_Unitario"]
    df_bcg["Margen_Porcentaje"] = df_bcg.apply(lambda x: (x["Margen_Unitario"] / x["Precio_Promedio"] * 100) if x["Precio_Promedio"] > 0 else 0, axis=1)

    # Limpieza
    df_final = df_bcg[df_bcg["Venta_Total"] > 0].copy()

    if df_final.empty:
        st.info("Sin datos suficientes.")
        return

    # 4. CLASIFICACIÓN
    promedio_popularidad = df_final["Unidades"].mean()
    promedio_margen = df_final["Margen_Unitario"].mean()

    def clasificar(row):
        pop = row["Unidades"]
        margen = row["Margen_Unitario"]
        if pop >= promedio_popularidad and margen >= promedio_margen: return "⭐ ESTRELLA"
        elif pop >= promedio_popularidad and margen < promedio_margen: return "🐄 VACA LECHERA"
        elif pop < promedio_popularidad and margen >= promedio_margen: return "🧩 INCÓGNITA"
        else: return "🐕 HUESO"

    df_final["Categoria"] = df_final.apply(clasificar, axis=1)

    # --- DASHBOARD VISUAL ---
    with col_kpi:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Estrellas", len(df_final[df_final["Categoria"]=="⭐ ESTRELLA"]))
        c2.metric("Vacas", len(df_final[df_final["Categoria"]=="🐄 VACA LECHERA"]))
        c3.metric("Incógnitas", len(df_final[df_final["Categoria"]=="🧩 INCÓGNITA"]))
        c4.metric("Huesos", len(df_final[df_final["Categoria"]=="🐕 HUESO"]))
        
        st.info(f"📊 **Promedios del Negocio:**\n\nPopularidad Media: **{int(promedio_popularidad)}** unds | Ganancia Media: **{formato_moneda(promedio_margen)}**")

    # --- GRÁFICO ---
    fig = go.Figure()
    colors = {"⭐ ESTRELLA": "#FFD700", "🐄 VACA LECHERA": "#00CC96", "🧩 INCÓGNITA": "#636EFA", "🐕 HUESO": "#EF553B"}
    
    for cat, color in colors.items():
        subset = df_final[df_final["Categoria"] == cat]
        if not subset.empty:
            fig.add_trace(go.Scatter(
                x=subset["Margen_Unitario"], y=subset["Unidades"],
                mode='markers+text', text=subset["Nombre_Plato"], textposition="top center",
                marker=dict(size=subset["Venta_Total"]/subset["Venta_Total"].max()*35 + 10, color=color),
                name=cat,
                hovertext=subset.apply(lambda r: f"<b>{r['Nombre_Plato']}</b><br>Ganancia: ${r['Margen_Unitario']:,.0f}<br>Ventas: {r['Unidades']}", axis=1)
            ))

    fig.add_vline(x=promedio_margen, line_dash="dash", line_color="white")
    fig.add_hline(y=promedio_popularidad, line_dash="dash", line_color="white")
    
    # Fondos Cuadrantes
    max_x = df_final["Margen_Unitario"].max() * 1.1
    max_y = df_final["Unidades"].max() * 1.1
    fig.add_shape(type="rect", x0=0, y0=0, x1=promedio_margen, y1=promedio_popularidad, fillcolor="red", opacity=0.1, layer="below", line_width=0)
    fig.add_shape(type="rect", x0=0, y0=promedio_popularidad, x1=promedio_margen, y1=max_y, fillcolor="green", opacity=0.1, layer="below", line_width=0)
    fig.add_shape(type="rect", x0=promedio_margen, y0=0, x1=max_x, y1=promedio_popularidad, fillcolor="blue", opacity=0.1, layer="below", line_width=0)
    fig.add_shape(type="rect", x0=promedio_margen, y0=promedio_popularidad, x1=max_x, y1=max_y, fillcolor="gold", opacity=0.1, layer="below", line_width=0)

    fig.update_layout(title="Mapa de Guerra (Tamaño = Venta Total)", xaxis_title="Ganancia ($)", yaxis_title="Popularidad (#)", height=550)
    st.plotly_chart(fig, use_container_width=True)

    # --- TABLAS SEPARADAS CON AYUDAS ---
    st.markdown("### 📋 Plan de Acción por Grupo")
    
    tab_est, tab_vac, tab_inc, tab_hue = st.tabs(["⭐ ESTRELLAS", "🐄 VACAS", "🧩 INCÓGNITAS", "🐕 HUESOS"])

    df_show = df_final.copy()
    # Formatos
    for c in ["Precio_Promedio", "Costo_Unitario", "Margen_Unitario", "Venta_Total"]:
        df_show[c] = df_show[c].apply(formato_moneda)
    df_show["Margen %"] = df_show["Margen_Porcentaje"].apply(lambda x: f"{x:.1f}%")
    
    cols = ["Nombre_Plato", "Precio_Promedio", "Costo_Unitario", "Margen_Unitario", "Margen %", "Unidades", "Venta_Total"]

    with tab_est:
        st.success("💡 **CONSEJO:** Estos platos son perfectos. **No les cambies el precio ni la receta.** Asegúrate de que el proveedor nunca falle con estos insumos.")
        df_e = df_show[df_show["Categoria"] == "⭐ ESTRELLA"].sort_values("Unidades", ascending=False)
        st.dataframe(df_e[cols], use_container_width=True, hide_index=True) if not df_e.empty else st.write("Ninguno.")

    with tab_vac:
        st.warning("💡 **CONSEJO:** Son muy populares pero ganas poco. **Sube el precio ligeramente** o renegocia el precio de la proteína/queso. ¡Aquí está el dinero!")
        df_v = df_show[df_show["Categoria"] == "🐄 VACA LECHERA"].sort_values("Unidades", ascending=False)
        st.dataframe(df_v[cols], use_container_width=True, hide_index=True) if not df_v.empty else st.write("Ninguno.")

    with tab_inc:
        st.info("💡 **CONSEJO:** Tienen un margen increíble pero nadie los pide. **¡Sugerencia del Chef!** Haz que los meseros lo ofrezcan o ponles una mejor foto en el menú.")
        df_i = df_show[df_show["Categoria"] == "🧩 INCÓGNITA"].sort_values("Margen_Unitario", ascending=False)
        st.dataframe(df_i[cols], use_container_width=True, hide_index=True) if not df_i.empty else st.write("Ninguno.")

    with tab_hue:
        st.error("💡 **CONSEJO:** Estos platos roban espacio en la nevera y tiempo en la cocina. **Sácalos de la carta** o transfórmalos completamente.")
        df_h = df_show[df_show["Categoria"] == "🐕 HUESO"].sort_values("Venta_Total", ascending=True)
        st.dataframe(df_h[cols], use_container_width=True, hide_index=True) if not df_h.empty else st.write("Ninguno.")