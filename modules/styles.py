import streamlit as st

def cargar_estilos():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Poppins', sans-serif;
        }

        /* --- FORZAR OCULTAR BARRA LATERAL --- */
        [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {
            display: none !important;
        }

        /* --- VARIABLES DE COLOR (Auto-adaptables) --- */
        :root {
            --card-bg: #ffffff;
            --card-text: #333333;
            --card-shadow: rgba(0, 0, 0, 0.1);
        }

        /* Detectar Modo Oscuro del Sistema/Navegador */
        @media (prefers-color-scheme: dark) {
            :root {
                --card-bg: #1e1e1e; /* Fondo oscuro para los cuadros */
                --card-text: #f8f9fa; /* Texto claro */
                --card-shadow: rgba(0, 0, 0, 0.5);
            }
        }

        /* --- TARJETAS DE MÉTRICAS (TOTALES) --- */
        div[data-testid="stMetric"] {
            background-color: var(--card-bg) !important;
            border: 2px solid #c5a065 !important;
            border-radius: 20px !important;
            padding: 20px !important;
            box-shadow: 0 8px 16px var(--card-shadow) !important;
            -webkit-box-shadow: 0 8px 16px var(--card-shadow) !important;
            display: block !important;
            width: 100% !important;
        }

        /* Texto dentro de las métricas */
        div[data-testid="stMetricLabel"] > div {
            color: var(--card-text) !important;
            font-size: 1rem !important;
            font-weight: 600 !important;
        }
        
        div[data-testid="stMetricValue"] > div {
            color: #D93838 !important; /* Mantenemos el rojo para resaltar valores */
            font-size: 1.8rem !important;
            font-weight: 700 !important;
        }

        /* --- TARJETAS DEL INICIO (DASHBOARD) --- */
        .card-modulo {
            background-color: var(--card-bg) !important;
            color: var(--card-text) !important;
            border: 2px solid #c5a065 !important;
            border-radius: 20px !important;
            padding: 20px !important;
            text-align: center !important;
            box-shadow: 0 4px 15px var(--card-shadow) !important;
            -webkit-box-shadow: 0 4px 15px var(--card-shadow) !important;
            margin-bottom: 10px !important;
            min-height: 180px !important;
            display: flex !important;
            flex-direction: column !important;
            justify-content: center !important;
            align-items: center !important;
        }

        .card-modulo h3 {
            color: #c5a065 !important; /* Títulos dorados en cards */
        }

        /* --- BOTONES --- */
        div.stButton > button {
            border-radius: 12px !important;
            border: 1px solid #c5a065 !important;
            border-bottom: 5px solid #c5a065 !important;
            background-color: var(--card-bg) !important;
            color: var(--card-text) !important;
            font-weight: 700 !important;
            -webkit-appearance: none !important;
        }

        button[kind="primary"] {
            background-color: #580f12 !important;
            color: white !important;
            border-bottom: 5px solid #3a080a !important;
        }

        /* --- TABLAS (DF) --- */
        div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {
            background-color: var(--card-bg) !important;
            border: 1px solid #c5a065 !important;
            border-radius: 15px !important;
        }

        /* --- LIMPIEZA --- */
        header, footer { visibility: hidden !important; }
    </style>
    """, unsafe_allow_html=True)
