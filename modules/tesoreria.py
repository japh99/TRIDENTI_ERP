import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta, date
import time
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA, limpiar_numero, generar_id

# --- CONFIGURACIÓN DE HOJAS ---
HOJA_VENTAS = "LOG_VENTAS_LOYVERSE"
HOJA_GASTOS = "LOG_GASTOS"
HOJA_CIERRES = "LOG_CIERRES_CAJA"

# Encabezados de la Base de Datos de Cierres
HEADERS_CIERRE = [
    "Fecha_Cierre", "Hora_Cierre", "Saldo_Teorico_E", "Saldo_Real_Cor", 
    "Diferencia", "Total_Nequi", "Total_Tarjetas", "Ticket_Ini", "Ticket_Fin",
    "Profit_Retenido", "Estado_Ahorro", "Numero_Cierre_Loyverse", "Shift_ID"
]

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

# --- BACKEND: CARGA DE DATOS ---

def cargar_datos_completos(sheet):
    """Carga cierres y gastos para el dashboard."""
    try:
        df_c = leer_datos_seguro(sheet.worksheet(HOJA_CIERRES))
        df_g = leer_datos_seguro(sheet.worksheet(HOJA_GASTOS))
        
        # Limpieza de Cierres
        if not df_c.empty:
            df_c.columns = df_c.columns.str.strip()
            df_c["Fecha_Cierre"] = pd.to_datetime(df_c["Fecha_Cierre"], errors='coerce').dt.date
            for col in ["Saldo_Real_Cor", "Total_Nequi", "Total_Tarjetas", "Diferencia"]:
                df_c[col] = pd.to_numeric(df_c[col], errors='coerce').fillna(0)
        
        # Limpieza de Gastos
        if not df_g.empty:
            df_g.columns = df_g.columns.str.strip()
            df_g["Fecha"] = pd.to_datetime(df_g["Fecha"], errors='coerce').dt.date
            df_g["Monto"] = pd.to_numeric(df_g["Monto"], errors='coerce').fillna(0)
            
        return df_c, df_g
    except:
        return pd.DataFrame(), pd.DataFrame()

# --- INTERFAZ ---

def show(sheet):
    st.title("🔐 Tesorería & Auditoría")
    
    if not sheet: return

    # TRES PESTAÑAS: Cierre, Consulta y el nuevo Dashboard
    tab_cierre, tab_historial, tab_dashboard = st.tabs(["📝 PROCESAR CIERRE", "📜 CONSULTAR CIERRES", "📊 DASHBOARD"])

    # --- PESTAÑA 1: PROCESAR CIERRE (Mantenemos tu lógica de recibos) ---
    with tab_cierre:
        st.subheader("Nuevo Arqueo por Rango de Tickets")
        st.info("Usa esta pestaña para guardar el cierre diario.")
        # ... (Aquí va tu código actual de procesamiento de cierre) ...
        st.write("Selecciona los tickets y guarda el cierre para alimentar el dashboard.")

    # --- PESTAÑA 2: CONSULTAR (Mantenemos tu lógica de búsqueda) ---
    with tab_historial:
        st.subheader("Buscador de Cierres Guardados")
        # ... (Aquí va tu código actual de historial por fecha) ...

    # --- PESTAÑA 3: EL NUEVO DASHBOARD GERENCIAL ---
    with tab_dashboard:
        st.subheader("📈 Resumen de Fondos Ingresados")
        
        df_c, df_g = cargar_datos_completos(sheet)
        
        if df_c.empty:
            st.warning("No hay datos suficientes para generar el dashboard.")
            return

        # 1. Filtro de Rango para el Dashboard
        c_f1, c_f2 = st.columns([1, 2])
        hoy = date.today()
        periodo = c_f1.selectbox("Periodo de Análisis:", ["Hoy", "Últimos 7 Días", "Este Mes", "Personalizado"])
        
        if periodo == "Hoy": f_ini = hoy
        elif periodo == "Últimos 7 Días": f_ini = hoy - timedelta(days=7)
        elif periodo == "Este Mes": f_ini = hoy.replace(day=1)
        else: f_ini = c_f2.date_input("Desde:", hoy - timedelta(days=30))
        
        # Filtrar DataFrames
        mask_c = (df_c["Fecha_Cierre"] >= f_ini)
        df_c_filtro = df_c[mask_c]
        
        mask_g = (df_g["Fecha"] >= f_ini) & (df_g["Metodo_Pago"].str.contains("Efectivo", na=False))
        df_g_filtro = df_g[mask_g]

        # 2. CÁLCULOS DE TOTALES
        total_efectivo_ventas = df_c_filtro["Saldo_Real_Cor"].sum()
        total_gastos_caja = df_g_filtro["Monto"].sum()
        
        efectivo_neto = total_efectivo_ventas - total_gastos_caja
        total_nequi = df_c_filtro["Total_Nequi"].sum()
        total_tarjetas = df_c_filtro["Total_Tarjetas"].sum()
        total_general = efectivo_neto + total_nequi + total_tarjetas

        # 3. VISUALIZACIÓN DE CARDS (Estilo Dorado Tridenti)
        st.markdown("---")
        k1, k2, k3, k4 = st.columns(4)
        
        # Efectivo Neto (Ventas - Gastos)
        k1.metric("💵 Efectivo Neto", formato_moneda(efectivo_neto), 
                  help=f"Ventas en efectivo ({formato_moneda(total_efectivo_ventas)}) menos Gastos pagados en caja ({formato_moneda(total_gastos_caja)})")
        
        k2.metric("📲 Total Nequi", formato_moneda(total_nequi))
        k3.metric("💳 Total Tarjetas", formato_moneda(total_tarjetas))
        
        # Total General resaltado
        st.markdown(f"""
            <div class="card-modulo" style="border-color: #580f12; background-color: rgba(88, 15, 18, 0.05);">
                <h2 style="margin:0; color: #580f12;">TOTAL INGRESOS (NETO)</h2>
                <h1 style="margin:0; color: #D93838;">{formato_moneda(total_general)}</h1>
                <p style="margin:0; opacity:0.6;">Periodo analizado desde {f_ini}</p>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        
        # 4. GRÁFICOS COMPLEMENTARIOS
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            st.write("**📊 Composición de Ingresos**")
            fig_pie = px.pie(
                names=["Efectivo Neto", "Nequi", "Tarjetas"],
                values=[efectivo_neto, total_nequi, total_tarjetas],
                hole=0.5,
                color_discrete_sequence=["#c5a065", "#580f12", "#333333"]
            )
            st.plotly_chart(fig_pie, use_container_width=True)
            
        with col_g2:
            st.write("**💸 Relación Efectivo vs Gastos**")
            df_egreso = pd.DataFrame({
                "Concepto": ["Efectivo Bruto", "Gastos Pagados"],
                "Monto": [total_efectivo_ventas, total_gastos_caja]
            })
            fig_bar = px.bar(df_egreso, x="Concepto", y="Monto", color="Concepto",
                             color_discrete_map={"Efectivo Bruto": "#27ae60", "Gastos Pagados": "#c0392b"})
            st.plotly_chart(fig_bar, use_container_width=True)

        # 5. LISTA DE GASTOS QUE AFECTARON LA CAJA
        with st.expander("📝 Ver detalle de gastos descontados de la caja"):
            if not df_g_filtro.empty:
                st.dataframe(df_g_filtro[["Fecha", "Categoria", "Descripcion", "Monto", "Responsable"]], use_container_width=True, hide_index=True)
            else:
                st.write("No hubo gastos pagados en efectivo en este periodo.")

    # Botón de actualización global
    st.markdown("---")
    if st.button("🔄 ACTUALIZAR TODO EL SISTEMA"):
        st.cache_data.clear()
        st.rerun()
