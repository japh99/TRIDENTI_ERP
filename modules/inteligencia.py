import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
import time
from utils import conectar_google_sheets, leer_datos_seguro, limpiar_numero, ZONA_HORARIA

# --- CONFIGURACIÓN DE HOJAS ---
HOJA_VENTAS = "LOG_VENTAS_LOYVERSE"
HOJA_RECETAS = "DB_RECETAS"
HOJA_INSUMOS = "DB_INSUMOS"
HOJA_CONFIG = "DB_CONFIG"

def formato_moneda_co(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

# --- FUNCIONES DE BACKEND ---

def obtener_total_gastos_fijos(sheet):
    """Suma todos los gastos fijos configurados en DB_CONFIG."""
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

def cargar_datos_maestros(sheet):
    """Calcula la rentabilidad cruzando Ventas, Recetas y Costos de Insumos."""
    try:
        # 1. Cargar Ventas
        ws_v = sheet.worksheet(HOJA_VENTAS)
        df_v = leer_datos_seguro(ws_v)
        if df_v.empty: return pd.DataFrame(), {}
        
        df_v["Fecha"] = pd.to_datetime(df_v["Fecha"], errors='coerce')
        df_v = df_v.dropna(subset=["Fecha"])
        df_v["Total_Dinero"] = pd.to_numeric(df_v["Total_Dinero"], errors='coerce').fillna(0)
        df_v["Cantidad_Vendida"] = pd.to_numeric(df_v["Cantidad_Vendida"], errors='coerce').fillna(0)

        # 2. Cargar Costos de Insumos
        ws_i = sheet.worksheet(HOJA_INSUMOS)
        df_i = leer_datos_seguro(ws_i)
        mapa_costos = dict(zip(df_i["Nombre_Insumo"], df_i["Costo_Promedio_Ponderado"].apply(limpiar_numero)))

        # 3. Cargar Recetas
        ws_r = sheet.worksheet(HOJA_RECETAS)
        df_r_raw = leer_datos_seguro(ws_r)
        
        costos_platos = {}
        if not df_r_raw.empty and len(df_r_raw.columns) >= 5:
            df_r = df_r_raw.iloc[:, [1, 3, 4]]
            df_r.columns = ["Nombre_Plato", "Ingrediente", "Cantidad"]
            
            for plato in df_r["Nombre_Plato"].unique():
                ings = df_r[df_r["Nombre_Plato"] == plato]
                costo_t = sum(mapa_costos.get(r["Ingrediente"], 0) * limpiar_numero(r["Cantidad"]) for _, r in ings.iterrows())
                costos_platos[plato] = costo_t

        # 4. Cruzar Costos con Ventas
        df_v["Costo_Receta"] = df_v["Nombre_Plato"].map(costos_platos).fillna(0)
        df_v["Costo_Total_Venta"] = df_v["Costo_Receta"] * df_v["Cantidad_Vendida"]
        df_v["Utilidad_Bruta"] = df_v["Total_Dinero"] - df_v["Costo_Total_Venta"]
        
        return df_v, costos_platos
    except Exception as e:
        st.error(f"Error en carga maestra: {e}")
        return pd.DataFrame(), {}

# --- INTERFAZ ---

def show(sheet):
    st.title("🧠 Inteligencia & Estrategia")
    st.markdown("---")
    
    if not sheet: return

    # Carga de datos base
    df_ventas, dict_costos = cargar_datos_maestros(sheet)
    total_fijos_mensuales = obtener_total_gastos_fijos(sheet)
    fijo_diario = total_fijos_mensuales / 30

    if df_ventas.empty:
        st.warning("⚠️ No se encontraron datos de ventas en el historial.")
        return

    # --- 1. SELECTOR DE TIEMPO (SIN RECTÁNGULO BLANCO) ---
    c_t1, c_t2 = st.columns([1, 2])
    
    with c_t1:
        predefinido = st.selectbox("📅 Periodo de Análisis:", 
            ["Hoy", "Últimos 7 Días", "Este Mes (Acumulado)", "Mes Anterior", "Todo el Historial", "Personalizado"])
    
    hoy = date.today()
    if predefinido == "Hoy":
        rango = [hoy, hoy]
    elif predefinido == "Últimos 7 Días":
        rango = [hoy - timedelta(days=7), hoy]
    elif predefinido == "Este Mes (Acumulado)":
        rango = [hoy.replace(day=1), hoy]
    elif predefinido == "Mes Anterior":
        ultimo_dia_mes_ant = hoy.replace(day=1) - timedelta(days=1)
        primer_dia_mes_ant = ultimo_dia_mes_ant.replace(day=1)
        rango = [primer_dia_mes_ant, ultimo_dia_mes_ant]
    elif predefinido == "Todo el Historial":
        rango = [df_ventas["Fecha"].min().date(), hoy]
    else:
        with c_t2:
            rango = st.date_input("Rango de Fechas:", [hoy - timedelta(days=30), hoy])

    # Filtrar datos según el rango seleccionado
    if isinstance(rango, (list, tuple)) and len(rango) == 2:
        df_p = df_ventas[(df_ventas["Fecha"].dt.date >= rango[0]) & (df_ventas["Fecha"].dt.date <= rango[1])].copy()
        n_dias = (rango[1] - rango[0]).days + 1
    else:
        # Caso de un solo día (o selección incompleta)
        fecha_unica = rango[0] if isinstance(rango, (list, tuple)) else rango
        df_p = df_ventas[df_ventas["Fecha"].dt.date == fecha_unica].copy()
        n_dias = 1

    if df_p.empty:
        st.info("No hay ventas registradas en el periodo seleccionado.")
        return

    # --- 2. MÉTRICAS PRINCIPALES DEL PERIODO ---
    v_total = df_p["Total_Dinero"].sum()
    c_total = df_p["Costo_Total_Venta"].sum()
    u_bruta = v_total - c_total
    gastos_fijos_prop = fijo_diario * n_dias
    u_neta = u_bruta - gastos_fijos_prop
    margen_n_pct = (u_neta / v_total) if v_total > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ventas", formato_moneda_co(v_total))
    c2.metric("Costo MP (Insumos)", f"- {formato_moneda_co(c_total)}")
    c3.metric("Gastos Fijos (Prop.)", f"- {formato_moneda_co(gastos_fijos_prop)}")
    c4.metric("UTILIDAD NETA", formato_moneda_co(u_neta), delta=f"{margen_n_pct*100:.1f}% Margen")

    st.markdown("---")

    # --- 3. PESTAÑAS DETALLADAS ---
    t1, t2, t3, t4 = st.tabs(["📈 Ventas", "🍔 Productos", "🕒 Horarios", "⚖️ PUNTO DE EQUILIBRIO"])

    with t1:
        # Gráfico Evolución
        df_diario = df_p.groupby(df_p["Fecha"].dt.date).agg({"Total_Dinero":"sum", "Utilidad_Bruta":"sum"}).reset_index()
        fig_evo = go.Figure()
        fig_evo.add_trace(go.Bar(x=df_diario["Fecha"], y=df_diario["Total_Dinero"], name="Ventas", marker_color='#c5a065'))
        fig_evo.add_trace(go.Scatter(x=df_diario["Fecha"], y=df_diario["Utilidad_Bruta"], name="Utilidad Bruta", line=dict(color='#D93838', width=3)))
        fig_evo.update_layout(title="Ventas vs Utilidad Bruta Diaria", barmode='overlay')
        st.plotly_chart(fig_evo, use_container_width=True)

    with t2:
        col_p1, col_p2 = st.columns(2)
        top_v = df_p.groupby("Nombre_Plato")["Total_Dinero"].sum().nlargest(10).reset_index()
        top_u = df_p.groupby("Nombre_Plato")["Utilidad_Bruta"].sum().nlargest(10).reset_index()
        
        with col_p1:
            st.plotly_chart(px.bar(top_v, x="Total_Dinero", y="Nombre_Plato", orientation='h', title="Top 10 por Ventas", color_discrete_sequence=['#580f12']), use_container_width=True)
        with col_p2:
            st.plotly_chart(px.bar(top_u, x="Utilidad_Bruta", y="Nombre_Plato", orientation='h', title="Top 10 más Rentables", color_discrete_sequence=['#27ae60']), use_container_width=True)

    with t3:
        # Análisis de Tiempo
        df_p["Hora_H"] = df_p["Hora"].apply(lambda x: int(str(x).split(':')[0]) if ':' in str(x) else 0)
        df_p["Nom_Dia"] = df_p["Fecha"].dt.day_name()
        df_hm = df_p.groupby(["Nom_Dia", "Hora_H"])["Total_Dinero"].sum().reset_index()
        fig_hm = px.density_heatmap(df_hm, x="Hora_H", y="Nom_Dia", z="Total_Dinero", title="Mapa de Calor de Ventas", color_continuous_scale="YlOrBr")
        st.plotly_chart(fig_hm, use_container_width=True)

    with t4:
        # --- DESARROLLO DEL PUNTO DE EQUILIBRIO ---
        st.subheader(f"Análisis de Supervivencia ({n_dias} días)")
        
        # Margen de contribución real del periodo
        margen_cont_pct = (u_bruta / v_total) if v_total > 0 else 0.35 
        
        # PE = Gastos Fijos Proporcionales / Margen %
        punto_eq = gastos_fijos_prop / margen_cont_pct if margen_cont_pct > 0 else 0
        
        col_pe1, col_pe2 = st.columns([2, 1])
        
        with col_pe1:
            # Gráfico de Velocímetro (Gauge)
            fig_pe = go.Figure(go.Indicator(
                mode = "gauge+number+delta",
                value = v_total,
                title = {'text': f"Venta Real vs Meta ({n_dias} d)"},
                delta = {'reference': punto_eq, 'increasing': {'color': "green"}},
                gauge = {
                    'axis': {'range': [None, max(punto_eq * 1.5, v_total * 1.1)]},
                    'bar': {'color': "#580f12"}, # Guinda
                    'bgcolor': "white",
                    'steps': [
                        {'range': [0, punto_eq], 'color': "#ffcccc"},
                        {'range': [punto_eq, punto_eq * 1.5], 'color': "#ccffcc"}
                    ],
                    'threshold': {'line': {'color': "black", 'width': 4}, 'thickness': 0.75, 'value': punto_eq}
                }
            ))
            st.plotly_chart(fig_pe, use_container_width=True)

        with col_pe2:
            st.markdown("### 📊 Estado Operativo")
            st.write(f"**Costos Fijos Periodo:** {formato_moneda_co(gastos_fijos_prop)}")
            st.write(f"**Venta Mínima:** {formato_moneda_co(punto_eq)}")
            
            if v_total >= punto_eq:
                dif = v_total - punto_eq
                st.success(f"**EN GANANCIA**\nSuperaste el punto por {formato_moneda_co(dif)}")
            else:
                falta = punto_eq - v_total
                st.error(f"**EN PÉRDIDA**\nTe faltan {formato_moneda_co(falta)} para cubrir el periodo.")

        # --- METAS DIARIAS ---
        st.markdown("---")
        meta_d = punto_eq / n_dias
        real_d = v_total / n_dias
        cumplimiento = (real_d / meta_d * 100) if meta_d > 0 else 0
        
        c_m1, c_m2, c_m3 = st.columns(3)
        c_m1.metric("Meta Venta Diaria", formato_moneda_co(meta_d))
        c_m2.metric("Venta Diaria Real", formato_moneda_co(real_d), delta=f"{cumplimiento-100:.1f}%")
        
        with c_m3:
            st.write(f"**Cumplimiento Meta:** {cumplimiento:.1f}%")
            st.progress(min(cumplimiento/100, 1.0))
