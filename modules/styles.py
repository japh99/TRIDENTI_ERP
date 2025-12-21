import streamlit as st

def cargar_estilos():
    st.markdown("""
    <style>
        /* --- FUENTE GLOBAL --- */
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');

        html, body, [data-testid="stAppViewContainer"] {
            font-family: 'Poppins', sans-serif;
        }

        /* --- FORZAR OCULTAR BARRA LATERAL Y CONTROLES --- */
        [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {
            display: none !important;
        }

        /* --- VARIABLES DE COLOR ADAPTATIVAS (CORRECCIÓN PARA MÓVIL) --- */
        :root {
            --bg-global: #ffffff;
            --card-bg: #ffffff;
            --card-text: #333333;
            --card-shadow: rgba(0, 0, 0, 0.1);
            --gold-tridenti: #c5a065;
            --guinda-tridenti: #580f12;
        }

        /* DETECCIÓN DE MODO OSCURO DEL SISTEMA */
        @media (prefers-color-scheme: dark) {
            :root {
                --bg-global: #0e1117; 
                --card-bg: #1e1e1e;
                --card-text: #f8f9fa;
                --card-shadow: rgba(0, 0, 0, 0.5);
            }
            
            /* FORZAR FONDO OSCURO EN CELULARES Y TABLETS */
            [data-testid="stAppViewContainer"], .main, body, [data-testid="stHeader"] {
                background-color: var(--bg-global) !important;
            }
            
            /* Texto de inputs en modo oscuro */
            .stTextInput>div>div>input, .stSelectbox>div>div>div {
                color: var(--card-text) !important;
            }
        }

        /* --- TARJETAS DE MÉTRICAS (TOTALES) --- */
        div[data-testid="stMetric"] {
            background-color: var(--card-bg) !important;
            border: 2px solid var(--gold-tridenti) !important;
            border-radius: 20px !important;
            padding: 20px !important;
            box-shadow: 0 8px 16px var(--card-shadow) !important;
            -webkit-box-shadow: 0 8px 16px var(--card-shadow) !important;
            display: block !important;
            width: 100% !important;
        }

        div[data-testid="stMetricLabel"] > div {
            color: var(--card-text) !important;
            font-size: 1rem !important;
            font-weight: 600 !important;
        }
        
        div[data-testid="stMetricValue"] > div {
            color: #D93838 !important; /* Rojo para resaltar montos */
            font-size: 1.8rem !important;
            font-weight: 700 !important;
        }

        /* --- TARJETAS DEL INICIO (DASHBOARD) --- */
        .card-modulo {
            background-color: var(--card-bg) !important;
            color: var(--card-text) !important;
            border: 2px solid var(--gold-tridenti) !important;
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
            transition: transform 0.3s ease;
        }

        .card-modulo:hover {
            transform: translateY(-5px);
            border-color: var(--guinda-tridenti) !important;
        }

        .card-modulo h3 {
            color: var(--gold-tridenti) !important;
            margin-top: 10px !important;
            font-weight: 700 !important;
        }

        /* --- BOTONES PREMIUM 3D --- */
        .stButton > button {
            border-radius: 12px !important;
            border: 1px solid var(--gold-tridenti) !important;
            border-bottom: 5px solid var(--gold-tridenti) !important;
            background-color: var(--card-bg) !important;
            color: var(--card-text) !important;
            font-weight: 700 !important;
            transition: all 0.1s ease;
            text-transform: uppercase;
            font-size: 0.8rem !important;
            -webkit-appearance: none !important;
        }

        .stButton > button:active {
            border-bottom: 2px solid var(--gold-tridenti) !important;
            transform: translateY(3px) !important;
        }

        /* Botón Primario (Cerrar Sesión / Registrar) */
        button[kind="primary"] {
            background-color: var(--guinda-tridenti) !important;
            color: white !important;
            border: 1px solid var(--guinda-tridenti) !important;
            border-bottom: 5px solid #3a080a !important;
        }

        /* --- TABLAS Y DATA EDITORS --- */
        div[data-testid="stDataFrame"], div[data-testid="stDataEditor"], .stTable {
            background-color: var(--card-bg) !important;
            border: 2px solid var(--gold-tridenti) !important;
            border-radius: 15px !important;
            overflow: hidden !important;
        }

        /* --- ELEMENTOS DE UI --- */
        .stAlert {
            border-radius: 15px !important;
        }

        /* Limpiar decoraciones de Streamlit */
        header, footer { visibility: hidden !important; }
        
    </style>
    """, unsafe_allow_html=True)
