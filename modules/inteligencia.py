import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
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

# --- BACKEND ---

def obtener_total_gastos_fijos(sheet):
    try:
        ws = sheet.worksheet(HOJA_CONFIG)
        df_config = leer_datos_seguro(ws)
        mask = df_config['Parametro'].str.startswith("GASTO_FIJO_", na=False)
        df_gastos = df_config[mask]
        total = 0.0
        for _, row in df_gastos.iterrows():
            valor_raw = str(row.get("Valor", "0")).split("|")[0]
            total += limpiar_numero(valor_raw)
        return total
    except: return 0.0

def cargar_datos_maestros(sheet):
    """Carga ventas, costos y recetas una sola vez."""
    try:
        # 1. Ventas
        ws_v = sheet.worksheet(HOJA_VENTAS)
        df_v = leer_datos_seguro(ws_v)
        if df_v.empty: return pd.DataFrame(), {}
        
        df_v["Fecha"] = pd.to_datetime(df_v["Fecha"], errors='coerce')
        df_v = df_v.dropna(subset=["Fecha"])
        df_v["Total_Dinero"] = pd.to_numeric(df_v["Total_Dinero"], errors='coerce').fillna(0)
        df_v["Cantidad_Vendida"] = pd.to_numeric(df_v["Cantidad_Vendida"], errors='coerce').fillna(0)

        # 2. Costos
        ws_i = sheet.worksheet(HOJA_INSUMOS)
        df_i = leer_datos_seguro(ws_i)
        mapa_costos = dict(zip(df_i["Nombre_Insumo"], df_i["Costo_Promedio_Ponderado"].apply(limpiar_numero)))

        ws_r = sheet.worksheet(HOJA_RECETAS)
        df_r = leer_datos_seguro(ws_r)
        
        costos_platos = {}
        if not df_r.empty and len(df_r.columns) >= 5:
            df_rec = df_r.iloc[:, [1, 3, 4]]
            df_rec.columns = ["Nombre_Plato", "Ingrediente", "Cantidad"]
            for plato in df_rec["Nombre_Plato"].unique():
                ings = df_rec[df_rec["Nombre_Plato"] == plato]
                costo_t = sum(mapa_costos.get(r["Ingrediente"], 0) * limpiar_numero(r["Cantidad"]) for _, r in ings.iterrows())
                costos_platos[plato] = costo_t

        df_v["Costo_Receta"] = df_v["Nombre_Plato"].map(costos_platos).fillna(0)
        df_v["Costo_Total_Venta"] = df_v["Costo_Receta"] * df_v["Cantidad_Vendida"]
        df_v["Utilidad_Bruta"] = df_v["Total_Dinero"] - df_v["Costo_Total_Venta"]
        
        return df_v, costos_platos
    except: return pd.DataFrame(), {}

# --- INTERFAZ ---

def show(sheet):
    st.title("🧠 Inteligencia & Estrategia")
    
    if not sheet: return

    # --- 1. FILTRO DE TIEMPO SUPERIOR ---
    with st.container():
        st.markdown('<div class="card-modulo" style="min-height: 50px; padding:15px;">', unsafe_allow_html=True)
        c_t1, c_t2 = st.columns([1, 2])
        
        with c_t1:
            predefinido = st.selectbox("📅 Seleccionar Periodo:", 
                ["Hoy", "Últimos 7 Días", "Este Mes (Acumulado)", "Mes Anterior", "Todo el Historial", "Personalizado"])
        
        # Lógica de fechas
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
            rango = [date(2024,1,1), hoy] # Fecha base
        else:
            with c_t2:
                rango = st.date_input("Rango Personalizado:", [hoy - timedelta(days=30), hoy])
        
        st.markdown('</div>', unsafe_allow_html=True)

    # Cargar Datos
    df_ventas, _ = cargar_datos_maestros(sheet)
    fijos_mensuales = obtener_total_gastos_fijos(sheet)
    fijo_diario = fijos_mensuales / 30

    if df_ventas.empty:
        st.warning("No hay datos de ventas para analizar.")
        return

    # Aplicar Filtro de Fecha
    if len(rango) == 2:
        df_p = df_ventas[(df_ventas["Fecha"].dt.date >= rango[0]) & (df_ventas["Fecha"].dt.date <= rango[1])].copy()
        n_dias = (rango[1] - rango[0]).days + 1
    else:
        df_p = df_ventas.copy(); n_dias = 1

    if df_p.empty:
        st.info(f"No se encontraron ventas entre el {rango[0]} y {rango[1]}.")
        return

    # --- 2. KPIs PRINCIPALES ---
    v_total = df_p["Total_Dinero"].sum()
    c_total = df_p["Costo_Total_Venta"].sum()
    u_bruta = v_total - c_total
    g_fijos_prop = fijo_diario * n_dias
    u_neta = u_bruta - g_fijos_prop
    margen_n_pct = (u_neta / v_total) if v_total > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ventas", formato_moneda_co(v_total))
    c2.metric("Costo MP", f"- {formato_moneda_co(c_total)}")
    c3.metric("Gastos Fijos", f"- {formato_moneda_co(g_fijos_prop)}")
    c4.metric("UTILIDAD NETA", formato_moneda_co(u_neta), delta=f"{margen_n_pct*100:.1f}% Margen")

    st.markdown("---")

    # --- 3. PESTAÑAS ---
    t1, t2, t3, t4 = st.tabs(["📈 Gráficos de Venta", "🍕 Análisis de Menú", "🕒 Horarios", "⚖️ PUNTO DE EQUILIBRIO"])

    with t1:
        # Venta Diaria
        df_d = df_p.groupby(df_p["Fecha"].dt.date)["Total_Dinero"].sum().reset_index()
        fig_d = px.area(df_d, x="Fecha", y="Total_Dinero", title="Flujo de Caja Diario", color_discrete_sequence=['#c5a065'])
        st.plotly_chart(fig_d, use_container_width=True)

    with t2:
        col_m1, col_m2 = st.columns(2)
        top_v = df_p.groupby("Nombre_Plato")["Total_Dinero"].sum().nlargest(10).reset_index()
        top_u = df_p.groupby("Nombre_Plato")["Utilidad_Bruta"].sum().nlargest(10).reset_index()
        col_m1.plotly_chart(px.bar(top_v, x="Total_Dinero", y="Nombre_Plato", orientation='h', title="Top 10 Ingresos", color_discrete_sequence=['#580f12']), use_container_width=True)
        col_m2.plotly_chart(px.bar(top_u, x="Utilidad_Bruta", y="Nombre_Plato", orientation='h', title="Top 10 Utilidad Real", color_discrete_sequence=['#27ae60']), use_container_width=True)

    with t3:
        # Mapa de Calor por Horas
        df_p["Hora_H"] = df_p["Hora"].apply(lambda x: int(str(x).split(':')[0]) if ':' in str(x) else 0)
        df_p["Nom_Dia"] = df_p["Fecha"].dt.day_name()
        df_hm = df_p.groupby(["Nom_Dia", "Hora_H"])["Total_Dinero"].sum().reset_index()
        fig_hm = px.density_heatmap(df_hm, x="Hora_H", y="Nom_Dia", z="Total_Dinero", title="Calor de Ventas por Hora", color_continuous_scale="YlOrBr")
        st.plotly_chart(fig_hm, use_container_width=True)

    with t4:
        # --- EL PUNTO DE EQUILIBRIO DESARROLLADO ---
        st.subheader(f"Análisis de Supervivencia ({n_dias} días analizados)")
        
        # Margen de contribución promedio del periodo
        margen_cont_pct = (u_bruta / v_total) if v_total > 0 else 0.35 # 35% por defecto si no hay ventas
        
        # PE = Gastos Fijos / Margen %
        punto_eq = g_fijos_prop / margen_cont_pct if margen_cont_pct > 0 else 0
        
        c_pe1, c_pe2 = st.columns([2, 1])
        
        with c_pe1:
            # Gráfico de Velocímetro (Gauge)
            fig_pe = go.Figure(go.Indicator(
                mode = "gauge+number+delta",
                value = v_total,
                title = {'text': "Venta Real vs Punto de Equilibrio"},
                delta = {'reference': punto_eq},
                gauge = {
                    'axis': {'range': [None, max(punto_eq * 1.5, v_total * 1.1)]},
                    'bar': {'color': "#580f12"},
                    'steps': [
                        {'range': [0, punto_eq], 'color': "#ff9999"},
                        {'range': [punto_eq, punto_eq * 1.5], 'color': "#99ff99"}
                    ],
                    'threshold': {'line': {'color': "black", 'width': 4}, 'thickness': 0.75, 'value': punto_eq}
                }
            ))
            st.plotly_chart(fig_pe, use_container_width=True)

        with c_pe2:
            st.markdown("### Resumen")
            st.write(f"**Costos Fijos del Periodo:** {formato_moneda_co(g_fijos_prop)}")
            st.write(f"**Venta Mínima Requerida:** {formato_moneda_co(punto_eq)}")
            st.write(f"**Venta Real Lograda:** {formato_moneda_co(v_total)}")
            
            if v_total >= punto_eq:
                st.success(f"🎊 Estás en zona de GANANCIA por {formato_moneda_co(v_total - punto_eq)}")
            else:
                st.error(f"🚨 Estás en zona de PÉRDIDA por {formato_moneda_co(punto_eq - v_total)}")

        # Meta Diaria
        st.markdown("---")
        meta_d = punto_eq / n_dias
        real_d = v_total / n_dias
        
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Meta de Venta Diaria", formato_moneda_co(meta_d))
        col_m2.metric("Venta Diaria Real", formato_moneda_co(real_d), delta=f"{((real_d/meta_d)-1)*100:.1f}%" if meta_d > 0 else "0%")
        col_m3.progress(min(real_d/meta_d, 1.0) if meta_d > 0 else 0)
        st.caption("Barra de cumplimiento de meta diaria.")
