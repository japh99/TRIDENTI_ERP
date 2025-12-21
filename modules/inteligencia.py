import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
from utils import conectar_google_sheets, leer_datos_seguro, limpiar_numero, ZONA_HORARIA

# --- CONFIGURACIÓN ---
HOJA_VENTAS = "LOG_VENTAS_LOYVERSE"
HOJA_RECETAS = "DB_RECETAS"
HOJA_INSUMOS = "DB_INSUMOS"
HOJA_CONFIG = "DB_CONFIG"

def formato_moneda_co(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

# --- BACKEND OPTIMIZADO ---

def obtener_total_gastos_fijos(sheet):
    try:
        ws = sheet.worksheet(HOJA_CONFIG)
        df_config = leer_datos_seguro(ws)
        if df_config.empty: return 0.0
        
        mask = df_config['Parametro'].str.startswith("GASTO_FIJO_", na=False)
        df_gastos = df_config[mask]
        
        total = 0.0
        for _, row in df_gastos.iterrows():
            valor_raw = str(row.get("Valor", "0")).split("|")[0]
            total += limpiar_numero(valor_raw)
        return total
    except: return 0.0

def cargar_datos_analisis(sheet):
    try:
        # 1. Cargar Ventas con limpieza de fechas robusta
        ws_v = sheet.worksheet(HOJA_VENTAS)
        df_v = leer_datos_seguro(ws_v)
        
        if df_v.empty: return pd.DataFrame(), {}

        # CORRECCIÓN DE FECHA: Intentar múltiples formatos
        df_v["Fecha"] = pd.to_datetime(df_v["Fecha"], errors='coerce')
        df_v = df_v.dropna(subset=["Fecha"]) # Quitar filas donde la fecha falló
        
        df_v["Total_Dinero"] = pd.to_numeric(df_v["Total_Dinero"], errors='coerce').fillna(0)
        df_v["Cantidad_Vendida"] = pd.to_numeric(df_v["Cantidad_Vendida"], errors='coerce').fillna(0)
        
        # Enriquecer datos de tiempo
        dias_es = {0: 'Lunes', 1: 'Martes', 2: 'Miércoles', 3: 'Jueves', 4: 'Viernes', 5: 'Sábado', 6: 'Domingo'}
        df_v["Dia_Semana"] = df_v["Fecha"].dt.dayofweek.map(dias_es)
        df_v["Dia_Index"] = df_v["Fecha"].dt.dayofweek
        df_v["Hora_Num"] = df_v["Hora"].apply(lambda x: int(str(x).split(':')[0]) if ':' in str(x) else 0)

        # 2. Cargar Costos (Insumos y Recetas)
        ws_i = sheet.worksheet(HOJA_INSUMOS)
        df_i = leer_datos_seguro(ws_i)
        mapa_costos = dict(zip(df_i["Nombre_Insumo"], df_i["Costo_Promedio_Ponderado"].apply(limpiar_numero)))

        ws_r = sheet.worksheet(HOJA_RECETAS)
        df_r_raw = leer_datos_seguro(ws_r)
        
        costos_platos = {}
        if not df_r_raw.empty and len(df_r_raw.columns) >= 5:
            df_r = df_r_raw.iloc[:, [1, 3, 4]]
            df_r.columns = ["Nombre_Plato", "Ingrediente", "Cantidad"]
            
            for plato in df_r["Nombre_Plato"].unique():
                ings = df_r[df_r["Nombre_Plato"] == plato]
                costo_t = 0
                for _, row in ings.iterrows():
                    c_ing = mapa_costos.get(row["Ingrediente"], 0)
                    cant = limpiar_numero(row["Cantidad"])
                    costo_t += c_ing * cant
                costos_platos[plato] = costo_t

        # Mapear costos a ventas
        df_v["Costo_Unitario_Receta"] = df_v["Nombre_Plato"].map(costos_platos).fillna(0)
        df_v["Costo_Total_Venta"] = df_v["Costo_Unitario_Receta"] * df_v["Cantidad_Vendida"]
        df_v["Utilidad_Bruta"] = df_v["Total_Dinero"] - df_v["Costo_Total_Venta"]
        
        return df_v, costos_platos

    except Exception as e:
        st.error(f"Error en procesamiento: {e}")
        return pd.DataFrame(), {}

# --- FRONTEND ---

def show(sheet):
    st.title("🧠 Inteligencia de Negocios & Estrategia")
    st.markdown("---")
    
    if not sheet: return

    with st.spinner("Procesando datos del historial..."):
        df_ventas, dict_costos = cargar_datos_analisis(sheet)
        total_fijos_mes = obtener_total_gastos_fijos(sheet)
        fijo_diario = total_fijos_mes / 30

    if df_ventas.empty:
        st.warning("⚠️ No se detectaron ventas válidas. Revisa el formato de fecha en tu Excel (debe ser AAAA-MM-DD o DD/MM/AAAA).")
        return

    # --- FILTROS ---
    min_d, max_d = df_ventas["Fecha"].min().date(), df_ventas["Fecha"].max().date()
    
    with st.sidebar:
        st.markdown("### 📅 Filtro de Fecha")
        rango = st.date_input("Periodo:", [min_d, max_d])
        if st.button("Limpiar Caché"):
            st.cache_data.clear()
            st.rerun()

    if len(rango) == 2:
        df_p = df_ventas[(df_ventas["Fecha"].dt.date >= rango[0]) & (df_ventas["Fecha"].dt.date <= rango[1])].copy()
        dias_n = (rango[1] - rango[0]).days + 1
    else:
        df_p = df_ventas.copy(); dias_n = 1

    # --- MÉTRICAS PRINCIPALES ---
    v_total = df_p["Total_Dinero"].sum()
    c_total = df_p["Costo_Total_Venta"].sum()
    u_bruta = v_total - c_total
    gastos_f = fijo_diario * dias_n
    u_neta = u_bruta - gastos_f
    margen_neto = (u_neta / v_total * 100) if v_total > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Ventas Totales", formato_moneda_co(v_total))
    c2.metric("📉 Costo Mercancía (MP)", formato_moneda_co(c_total))
    c3.metric("🏢 Gastos Fijos (Prop.)", formato_moneda_co(gastos_f))
    c4.metric("🏆 UTILIDAD NETA", formato_moneda_co(u_neta), delta=f"{margen_neto:.1} % Margen")

    st.markdown("---")

    t1, t2, t3, t4 = st.tabs(["📈 Ventas y Utilidad", "🍔 Productos y Menú", "🕒 Análisis de Tiempo", "⚖️ Punto de Equilibrio"])

    with t1:
        # Gráfico de Ventas Diarias vs Utilidad
        df_diario = df_p.groupby(df_p["Fecha"].dt.date).agg({"Total_Dinero":"sum", "Utilidad_Bruta":"sum"}).reset_index()
        fig_evolucion = go.Figure()
        fig_evolucion.add_trace(go.Bar(x=df_diario["Fecha"], y=df_diario["Total_Dinero"], name="Venta Bruta", marker_color='#c5a065'))
        fig_evolucion.add_trace(go.Scatter(x=df_diario["Fecha"], y=df_diario["Utilidad_Bruta"], name="Utilidad Bruta", line=dict(color='#D93838', width=3)))
        fig_evolucion.update_layout(title="Evolución Diaria: Ventas vs Utilidad", barmode='overlay')
        st.plotly_chart(fig_evolucion, use_container_width=True)

    with t2:
        col_p1, col_p2 = st.columns(2)
        
        with col_p1:
            # Top 10 Platos que más dinero traen
            top_platos_v = df_p.groupby("Nombre_Plato")["Total_Dinero"].sum().sort_values(ascending=False).head(10).reset_index()
            fig_top_v = px.bar(top_platos_v, x="Total_Dinero", y="Nombre_Plato", orientation='h', 
                               title="Top 10 Platos (Por Ingresos)", color_discrete_sequence=['#580f12'])
            st.plotly_chart(fig_top_v, use_container_width=True)

        with col_p2:
            # Top 10 Platos más rentables (Margen)
            top_platos_r = df_p.groupby("Nombre_Plato")["Utilidad_Bruta"].sum().sort_values(ascending=False).head(10).reset_index()
            fig_top_r = px.bar(top_platos_r, x="Utilidad_Bruta", y="Nombre_Plato", orientation='h', 
                               title="Top 10 Platos (Por Utilidad Real)", color_discrete_sequence=['#27ae60'])
            st.plotly_chart(fig_top_r, use_container_width=True)

    with t3:
        col_t1, col_t2 = st.columns(2)
        
        with col_t1:
            # Ventas por Día de la Semana
            ventas_dia = df_p.groupby(["Dia_Index", "Dia_Semana"])["Total_Dinero"].sum().reset_index().sort_values("Dia_Index")
            fig_dias = px.line(ventas_dia, x="Dia_Semana", y="Total_Dinero", title="Ventas por Día de la Semana", markers=True)
            st.plotly_chart(fig_dias, use_container_width=True)
            
        with col_t2:
            # Mapa de Calor por Horas
            df_calor = df_p.groupby(["Dia_Semana", "Hora_Num"])["Total_Dinero"].sum().reset_index()
            fig_calor = px.density_heatmap(df_calor, x="Hora_Num", y="Dia_Semana", z="Total_Dinero", 
                                           title="Concentración de Ventas (Calor)", color_continuous_scale="YlOrBr")
            st.plotly_chart(fig_calor, use_container_width=True)

    with t4:
        st.subheader("Análisis de Supervivencia (Punto de Equilibrio)")
        margen_contribucion_total = u_bruta / v_total if v_total > 0 else 0
        pe_periodo = gastos_f / margen_contribucion_total if margen_contribucion_total > 0 else 0
        
        progreso_pe = min(v_total / pe_periodo, 1.0) if pe_periodo > 0 else 0
        
        st.write(f"Para cubrir tus costos de **{formato_moneda_co(gastos_f)}** en este periodo, necesitabas vender **{formato_moneda_co(pe_periodo)}**.")
        st.progress(progreso_pe)
        st.write(f"Progreso hacia el punto de equilibrio: **{progreso_pe*100:.1f}%**")
        
        if v_total > pe_periodo:
            st.success(f"🎊 Estás en zona de GANANCIA. Has superado el punto de equilibrio por {formato_moneda_co(v_total - pe_periodo)}.")
        else:
            st.error(f"⚠️ Estás en zona de PÉRDIDA. Te faltan {formato_moneda_co(pe_periodo - v_total)} para cubrir los costos fijos.")
