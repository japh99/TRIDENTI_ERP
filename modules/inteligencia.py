import streamlit as st
import pandas as pd
import plotly.express as px
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

# --- CARGA DE DATOS UNIFICADA ---
@st.cache_data(ttl=300)
def cargar_todo(data_ventas, data_recetas, data_insumos):
    try:
        # 1. Procesar Ventas
        df_v = pd.DataFrame(data_ventas)
        df_v["Fecha"] = pd.to_datetime(df_v["Fecha"])
        df_v["Total_Dinero"] = pd.to_numeric(df_v["Total_Dinero"], errors='coerce').fillna(0)
        df_v["Cantidad_Vendida"] = pd.to_numeric(df_v["Cantidad_Vendida"], errors='coerce').fillna(0)
        
        # Enriquecer Ventas para Dashboard Visual
        dias_es = {0: 'Lunes', 1: 'Martes', 2: 'Miércoles', 3: 'Jueves', 4: 'Viernes', 5: 'Sábado', 6: 'Domingo'}
        df_v["Dia_Semana"] = df_v["Fecha"].dt.dayofweek.map(dias_es)
        df_v["Dia_Index"] = df_v["Fecha"].dt.dayofweek
        # Extraer hora solo si existe y es válida
        df_v["Hora_Num"] = df_v["Hora"].apply(lambda x: int(str(x).split(':')[0]) if ':' in str(x) else 0)

        # 2. Procesar Recetas (Para BCG)
        df_r = pd.DataFrame(data_recetas[1:], columns=data_recetas[0])
        if len(df_r.columns) >= 5:
            df_r = df_r.iloc[:, [1, 3, 4]]
            df_r.columns = ["Nombre_Plato", "Ingrediente", "Cantidad"]
        else:
            df_r = pd.DataFrame(columns=["Nombre_Plato", "Ingrediente", "Cantidad"])

        # 3. Procesar Insumos (Para Costos)
        df_i = pd.DataFrame(data_insumos)
        df_i["Costo_Promedio_Ponderado"] = df_i["Costo_Promedio_Ponderado"].apply(limpiar_numero)
        
        # 4. Calcular Costos
        costos_platos = {}
        if not df_i.empty:
            mapa_costos = dict(zip(df_i["Nombre_Insumo"], df_i["Costo_Promedio_Ponderado"]))
            
            for plato in df_r["Nombre_Plato"].unique():
                ings = df_r[df_r["Nombre_Plato"] == plato]
                costo = 0
                for _, row in ings.iterrows():
                    ins = row["Ingrediente"]
                    try: cant = float(str(row["Cantidad"]).replace(",", "."))
                    except: cant = 0
                    costo += mapa_costos.get(ins, 0) * cant
                costos_platos[plato] = costo
                
        return df_v, costos_platos

    except Exception as e:
        return pd.DataFrame(), {}

# --- GESTIÓN GASTOS FIJOS ---
def cargar_gastos_fijos(sheet):
    try:
        ws = sheet.worksheet(HOJA_CONFIG)
        data = ws.get_all_records()
        gastos = []
        defaults = ["Arriendo Local", "Nómina Fija", "Servicios Públicos", "Internet / Software", "Marketing", "Mantenimiento", "Otros"]
        encontrados = []

        for row in data:
            param = str(row.get("Parametro", ""))
            if param.startswith("GASTO_FIJO_"):
                nom = param.replace("GASTO_FIJO_", "").replace("_", " ")
                val_raw = str(row.get("Valor", "0"))
                val, dia = (val_raw.split("|") if "|" in val_raw else (val_raw, "1"))
                gastos.append({"Gasto": nom, "Valor ($)": limpiar_numero(val), "Día Pago": int(limpiar_numero(dia))})
                encontrados.append(nom)
        
        for d in defaults:
            if d not in encontrados: gastos.append({"Gasto": d, "Valor ($)": 0.0, "Día Pago": 1})
            
        return pd.DataFrame(gastos)
    except: return pd.DataFrame(columns=["Gasto", "Valor ($)", "Día Pago"])

def guardar_gastos_fijos(sheet, df):
    try:
        ws = sheet.worksheet(HOJA_CONFIG)
        for _, row in df.iterrows():
            p = f"GASTO_FIJO_{row['Gasto'].replace(' ', '_')}"
            v = f"{row['Valor ($)']}|{int(row['Día Pago'])}"
            cell = ws.find(p)
            if cell: ws.update_cell(cell.row, 2, v)
            else: ws.append_row([p, v])
        return True
    except: return False

# --- INTERFAZ ---
def show(sheet):
    st.title("🧠 Inteligencia de Negocios")
    st.markdown("---")
    if not sheet: return

    # 1. ALERTAS DE PAGO
    hoy = datetime.now().day
    df_gastos = cargar_gastos_fijos(sheet)
    alertas = []
    if hoy in [14, 15, 16, 29, 30, 31]:
        nom = df_gastos[df_gastos["Gasto"].str.contains("Nómina", case=False)]
        if not nom.empty and nom.iloc[0]["Valor ($)"] > 0:
            alertas.append(f"👷 **QUINCENA:** Prepara {formato_moneda_co(nom.iloc[0]['Valor ($)']/2)}")
            
    for _, r in df_gastos.iterrows():
        if "Nómina" in r["Gasto"]: continue
        if int(r["Día Pago"]) == hoy: alertas.append(f"📅 **HOY SE PAGA:** {r['Gasto']}")
    
    if alertas:
        with st.container(border=True):
            st.write("🔔 **Agenda Financiera**")
            for a in alertas: st.warning(a)

    # 2. CARGA
    with st.spinner("Procesando datos..."):
        try:
            ws_v = sheet.worksheet(HOJA_VENTAS)
            ws_r = sheet.worksheet(HOJA_RECETAS)
            ws_i = sheet.worksheet(HOJA_INSUMOS)
            df_ventas, dict_costos = cargar_todo(ws_v.get_all_records(), ws_r.get_all_values(), ws_i.get_all_records())
        except: return

    # 3. FILTROS
    with st.expander("🔎 Configuración de Análisis", expanded=True):
        c1, c2 = st.columns(2)
        if not df_ventas.empty:
            min_d, max_d = df_ventas["Fecha"].min().date(), df_ventas["Fecha"].max().date()
            rango = c1.date_input("Rango Fechas:", [min_d, max_d])
            if len(rango) == 2:
                df_p = df_ventas[(df_ventas["Fecha"].dt.date >= rango[0]) & (df_ventas["Fecha"].dt.date <= rango[1])]
                c2.info(f"📊 Analizando **{df_p['Fecha'].dt.date.nunique()} días** de ventas.")
            else: df_p = df_ventas
        else:
            df_p = pd.DataFrame()
            st.warning("Sin ventas.")

    # --- PESTAÑAS (AQUÍ RECUPERAMOS LO VISUAL) ---
    tab1, tab2, tab3 = st.tabs(["📊 DASHBOARD VENTAS", "🚀 MATRIZ BCG", "⚖️ EQUILIBRIO & GASTOS"])

    # === TAB 1: LO QUE TE GUSTABA (VISUAL) ===
    with tab1:
        if not df_p.empty:
            # KPIs
            tot = df_p["Total_Dinero"].sum()
            tik = df_p["Numero_Recibo"].nunique()
            prom = tot/tik if tik>0 else 0
            
            k1, k2, k3 = st.columns(3)
            k1.metric("Venta Total", formato_moneda_co(tot))
            k2.metric("Tickets", tik)
            k3.metric("Ticket Promedio", formato_moneda_co(prom))
            
            st.markdown("---")
            
            # GRÁFICOS
            c_g1, c_g2 = st.columns(2)
            with c_g1:
                st.subheader("📅 Ventas por Día")
                df_dia = df_p.groupby("Dia_Semana")["Total_Dinero"].sum().reindex(['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo']).reset_index()
                fig_d = px.bar(df_dia, x="Dia_Semana", y="Total_Dinero", color="Dia_Semana")
                st.plotly_chart(fig_d, use_container_width=True)
                
            with c_g2:
                st.subheader("🔥 Mapa de Calor (Horas)")
                df_h = df_p.groupby(["Dia_Index", "Dia_Semana", "Hora_Num"])["Total_Dinero"].sum().reset_index().sort_values("Dia_Index")
                fig_h = px.density_heatmap(df_h, x="Hora_Num", y="Dia_Semana", z="Total_Dinero", nbinsx=14, color_continuous_scale="Magma")
                st.plotly_chart(fig_h, use_container_width=True)
            
            st.subheader("💳 Métodos de Pago")
            df_pay = df_p.groupby("Metodo_Pago_Loyverse")["Total_Dinero"].sum().reset_index()
            fig_p = px.pie(df_pay, values="Total_Dinero", names="Metodo_Pago_Loyverse", hole=0.4)
            st.plotly_chart(fig_p, use_container_width=True)
            
        else: st.info("No hay datos para mostrar en el Dashboard.")

    # === TAB 2: ESTRATEGIA (BCG) ===
    with tab2:
        if not df_p.empty:
            df_bcg = df_p.groupby("Nombre_Plato").agg(Und=('Cantidad_Vendida','sum'), Venta=('Total_Dinero','sum')).reset_index()
            # Limpieza
            df_bcg = df_bcg[df_bcg["Venta"] > 0]
            
            df_bcg["Precio"] = df_bcg["Venta"] / df_bcg["Und"]
            df_bcg["Costo"] = df_bcg["Nombre_Plato"].map(dict_costos).fillna(0)
            df_bcg["Margen"] = df_bcg["Precio"] - df_bcg["Costo"]
            
            # Solo mostramos BCG si hay costos cargados
            if df_bcg["Costo"].sum() > 0:
                avg_u = df_bcg["Und"].mean()
                avg_m = df_bcg["Margen"].mean()
                
                def clasif(r):
                    if r["Und"]>=avg_u and r["Margen"]>=avg_m: return "⭐ ESTRELLA"
                    if r["Und"]>=avg_u: return "🐄 VACA LECHERA"
                    if r["Margen"]>=avg_m: return "🧩 INCÓGNITA"
                    return "🐕 HUESO"
                
                df_bcg["Cat"] = df_bcg.apply(clasif, axis=1)
                
                fig_b = px.scatter(df_bcg, x="Margen", y="Und", color="Cat", size="Venta", hover_name="Nombre_Plato",
                                   color_discrete_map={"⭐ ESTRELLA":"#f1c40f", "🐄 VACA LECHERA":"#2ecc71", "🧩 INCÓGNITA":"#3498db", "🐕 HUESO":"#e74c3c"})
                fig_b.add_vline(x=avg_m, line_dash="dash"); fig_b.add_hline(y=avg_u, line_dash="dash")
                st.plotly_chart(fig_b, use_container_width=True)
                
                st.dataframe(df_bcg[["Nombre_Plato", "Cat", "Margen", "Und", "Venta"]].sort_values("Venta", ascending=False), use_container_width=True)
            else:
                st.warning("⚠️ No se puede generar la Matriz BCG porque **no hay costos configurados** en Recetas/Insumos.")
                st.info("Sin embargo, puedes ver el Dashboard de Ventas en la Pestaña 1.")

    # === TAB 3: EQUILIBRIO ===
    with tab3:
        # Editor Gastos
        with st.expander("📝 Editar Gastos Fijos", expanded=False):
            df_ed = st.data_editor(df_gastos, num_rows="dynamic", use_container_width=True, key="ed_gastos")
            if st.button("💾 Guardar Gastos"):
                if guardar_gastos_fijos(sheet, df_ed):
                    st.cache_data.clear(); st.success("Guardado"); time.sleep(1); st.rerun()
        
        total_fijos = df_ed["Valor ($)"].sum()
        
        # Margen Global
        margen_global = 0.35
        if 'df_bcg' in locals() and not df_bcg.empty and df_bcg["Costo"].sum() > 0:
            tv = df_bcg["Venta"].sum()
            tc = (df_bcg["Costo"] * df_bcg["Und"]).sum()
            if tv > 0: margen_global = (tv - tc) / tv
            
        pe_mensual = total_fijos / margen_global if margen_global > 0 else 0
        pe_diario = pe_mensual / 30
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Gastos Fijos", formato_moneda_co(total_fijos))
        c2.metric("Meta Mensual", formato_moneda_co(pe_mensual))
        c3.metric("Meta Diaria", formato_moneda_co(pe_diario))
        
        # Progreso
        v_prom = df_p.groupby(df_p["Fecha"].dt.date)["Total_Dinero"].sum().mean() if not df_p.empty else 0
        st.write(f"Venta Promedio Actual: **{formato_moneda_co(v_prom)}**")
        if pe_diario > 0:
            pct = min(v_prom / pe_diario, 1.0)
            st.progress(pct, text=f"Cubrimiento: {pct*100:.1f}%")