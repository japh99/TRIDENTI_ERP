import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import time
from utils import conectar_google_sheets, leer_datos_seguro, limpiar_numero

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
        data = ws.get_all_records()
        total = 0.0
        for row in data:
            param = str(row.get("Parametro", ""))
            if param.startswith("GASTO_FIJO_"):
                valor_raw = str(row.get("Valor", "0")).split("|")[0]
                total += limpiar_numero(valor_raw)
        return total
    except: return 0.0

@st.cache_data(ttl=300)
def cargar_datos_analisis(_sheet):
    try:
        # 1. Ventas
        ws_v = _sheet.worksheet(HOJA_VENTAS)
        df_v = pd.DataFrame(ws_v.get_all_records())
        
        if not df_v.empty:
            df_v["Fecha"] = pd.to_datetime(df_v["Fecha"])
            df_v["Total_Dinero"] = pd.to_numeric(df_v["Total_Dinero"], errors='coerce').fillna(0)
            df_v["Cantidad_Vendida"] = pd.to_numeric(df_v["Cantidad_Vendida"], errors='coerce').fillna(0)
            
            dias_es = {0: 'Lunes', 1: 'Martes', 2: 'Miércoles', 3: 'Jueves', 4: 'Viernes', 5: 'Sábado', 6: 'Domingo'}
            df_v["Dia_Semana"] = df_v["Fecha"].dt.dayofweek.map(dias_es)
            df_v["Dia_Index"] = df_v["Fecha"].dt.dayofweek
            df_v["Hora_Num"] = df_v["Hora"].apply(lambda x: int(str(x).split(':')[0]) if ':' in str(x) else 0)

        # 2. Insumos
        ws_i = _sheet.worksheet(HOJA_INSUMOS)
        df_i = pd.DataFrame(ws_i.get_all_records())
        df_i["Costo_Promedio_Ponderado"] = df_i["Costo_Promedio_Ponderado"].apply(limpiar_numero)
        mapa_costos = dict(zip(df_i["Nombre_Insumo"], df_i["Costo_Promedio_Ponderado"]))

        # 3. Recetas
        ws_r = _sheet.worksheet(HOJA_RECETAS)
        raw_r = ws_r.get_all_values()
        
        costos_platos = {}
        if len(raw_r) > 1:
            df_r = pd.DataFrame(raw_r[1:], columns=raw_r[0])
            if len(df_r.columns) >= 5:
                df_r = df_r.iloc[:, [1, 3, 4]]
                df_r.columns = ["Nombre_Plato", "Ingrediente", "Cantidad"]
            
            for plato in df_r["Nombre_Plato"].unique():
                ings = df_r[df_r["Nombre_Plato"] == plato]
                costo = 0
                for _, row in ings.iterrows():
                    ins = row["Ingrediente"]
                    try: cant = float(str(row["Cantidad"]).replace(",", "."))
                    except: cant = 0
                    costo += mapa_costos.get(ins, 0) * cant
                costos_platos[plato] = costo
        
        # 4. Enriquecer Ventas con Costo Individual
        if not df_v.empty:
            df_v["Costo_Unitario_Receta"] = df_v["Nombre_Plato"].map(costos_platos).fillna(0)
            df_v["Costo_Total_Venta"] = df_v["Costo_Unitario_Receta"] * df_v["Cantidad_Vendida"]
            
        return df_v, costos_platos

    except: return pd.DataFrame(), {}

# --- FRONTEND ---
def show(sheet):
    st.title("🧠 Inteligencia & Estrategia")
    st.markdown("---")
    if not sheet: return

    with st.spinner("Procesando datos..."):
        df_ventas, dict_costos = cargar_datos_analisis(sheet)
        total_gastos_fijos_mensual = obtener_total_gastos_fijos(sheet)
        gasto_fijo_diario = total_gastos_fijos_mensual / 30

    # FILTROS
    with st.expander("🔎 Filtro de Fechas", expanded=False):
        c1, c2 = st.columns(2)
        if not df_ventas.empty:
            min_d, max_d = df_ventas["Fecha"].min().date(), df_ventas["Fecha"].max().date()
            rango = c1.date_input("Periodo:", [min_d, max_d])
            if len(rango) == 2:
                df_p = df_ventas[(df_ventas["Fecha"].dt.date >= rango[0]) & (df_ventas["Fecha"].dt.date <= rango[1])]
                dias_analisis = (rango[1] - rango[0]).days + 1
                c2.info(f"Analizando **{dias_analisis} días**.")
            else:
                df_p = df_ventas; dias_analisis = 1
        else:
            df_p = pd.DataFrame(); dias_analisis = 0; st.warning("Sin ventas.")

    tab_utilidad, tab_dash, tab_pe = st.tabs(["💰 P&L (UTILIDAD REAL)", "📊 DASHBOARD VENTAS", "⚖️ PUNTO DE EQUILIBRIO"])

    # --- TAB 1: P&L ---
    with tab_utilidad:
        st.subheader("Estado de Resultados Operativo")
        
        if not df_p.empty:
            # 1. CÁLCULOS
            venta_total = df_p["Total_Dinero"].sum()
            # AQUÍ SE DESCUENTA EL COSTO DEL PRODUCTO
            costo_mercancia = df_p["Costo_Total_Venta"].sum() 
            
            utilidad_bruta = venta_total - costo_mercancia
            gasto_fijo_periodo = gasto_fijo_diario * dias_analisis
            utilidad_neta = utilidad_bruta - gasto_fijo_periodo
            margen_neto_pct = (utilidad_neta / venta_total * 100) if venta_total > 0 else 0
            
            # 2. TARJETAS
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("1. Ventas", formato_moneda_co(venta_total))
            col2.metric("2. Costo Recetas (CMV)", f"- {formato_moneda_co(costo_mercancia)}", help="Suma del costo de ingredientes de cada plato vendido.")
            col3.metric("3. Carga Fabril (Fijos)", f"- {formato_moneda_co(gasto_fijo_periodo)}", help=f"Proporcional a {dias_analisis} días.")
            col4.metric("4. UTILIDAD NETA", formato_moneda_co(utilidad_neta), delta=f"{margen_neto_pct:.1f}% Margen")
            
            st.markdown("---")
            
            # --- SECCIÓN DE VERIFICACIÓN DE COSTOS (NUEVO) ---
            # Detectar qué productos se vendieron pero tienen costo 0 (Sin Receta)
            productos_sin_costo = df_p[df_p["Costo_Unitario_Receta"] == 0]["Nombre_Plato"].unique()
            
            if len(productos_sin_costo) > 0:
                st.error(f"⚠️ ALERTA DE COSTOS: Hay {len(productos_sin_costo)} productos vendidos que tienen COSTO $0.")
                st.caption("Esto infla artificialmente tu utilidad. Crea las recetas para estos productos:")
                with st.expander("Ver productos sin receta"):
                    st.dataframe(pd.DataFrame(productos_sin_costo, columns=["Producto sin Costo"]), use_container_width=True)
            else:
                st.success("✅ Excelente: Todos los productos vendidos tienen receta y costo asignado.")

            st.markdown("---")
            
            # Gráfico de Cascada
            df_diario = df_p.groupby(df_p["Fecha"].dt.date).agg({"Total_Dinero": "sum", "Costo_Total_Venta": "sum"}).reset_index()
            df_diario["Utilidad_Bruta"] = df_diario["Total_Dinero"] - df_diario["Costo_Total_Venta"]
            
            fig_util = go.Figure()
            fig_util.add_trace(go.Bar(x=df_diario["Fecha"], y=df_diario["Total_Dinero"], name="Ventas", marker_color="#2ecc71"))
            fig_util.add_trace(go.Bar(x=df_diario["Fecha"], y=df_diario["Costo_Total_Venta"], name="Costo Insumos", marker_color="#e74c3c"))
            fig_util.add_trace(go.Scatter(x=df_diario["Fecha"], y=df_diario["Utilidad_Bruta"], name="Ganancia Bruta", line=dict(color='blue', width=3)))
            
            fig_util.update_layout(title="Dinero que entra vs. Dinero que cuesta (Por Día)", barmode='group')
            st.plotly_chart(fig_util, use_container_width=True)

    # --- TAB 2: DASHBOARD ---
    with tab_dash:
        if not df_p.empty:
            k1, k2 = st.columns(2)
            k1.metric("Tickets", df_p["Numero_Recibo"].nunique())
            
            g1, g2 = st.columns(2)
            with g1:
                st.caption("Mapa de Calor")
                df_h = df_p.groupby(["Dia_Index", "Dia_Semana", "Hora_Num"])["Total_Dinero"].sum().reset_index().sort_values("Dia_Index")
                st.plotly_chart(px.density_heatmap(df_h, x="Hora_Num", y="Dia_Semana", z="Total_Dinero", color_continuous_scale="Magma"), use_container_width=True)
            with g2:
                st.caption("Métodos de Pago")
                df_pay = df_p.groupby("Metodo_Pago_Loyverse")["Total_Dinero"].sum().reset_index()
                st.plotly_chart(px.pie(df_pay, values="Total_Dinero", names="Metodo_Pago_Loyverse", hole=0.4), use_container_width=True)

    # --- TAB 3: PUNTO DE EQUILIBRIO ---
    with tab_pe:
        st.subheader("Metas de Venta")
        if total_gastos_fijos_mensual > 0:
            margen_global_pct = 0.35
            if not df_p.empty:
                v_tot = df_p["Total_Dinero"].sum()
                c_tot = df_p["Costo_Total_Venta"].sum()
                if v_tot > 0: margen_global_pct = (v_tot - c_tot) / v_tot

            pe_mensual = total_gastos_fijos_mensual / margen_global_pct if margen_global_pct > 0 else 0
            pe_diario = pe_mensual / 30
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Gastos Fijos", formato_moneda_co(total_gastos_fijos_mensual))
            c2.metric("Margen Global", f"{margen_global_pct*100:.1f}%")
            c3.metric("META DIARIA", formato_moneda_co(pe_diario))
            
            if not df_p.empty:
                prom_real = df_p.groupby(df_p["Fecha"].dt.date)["Total_Dinero"].sum().mean() or 0
                st.write(f"Promedio Actual: **{formato_moneda_co(prom_real)}**")
                st.progress(min(prom_real / pe_diario, 1.0) if pe_diario > 0 else 0)
        else:
            st.warning("Configura tus Gastos Fijos en 'Financiero'.")