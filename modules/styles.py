import streamlit as st

def cargar_estilos():
    st.markdown("""
    <style>
        /* --- 1. FUENTES Y COLORES GLOBALES --- */
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap');

        :root {
            --primary: #580f12;       /* Vino Tinto */
            --primary-hover: #7a1519; /* Vino más claro */
            --gold: #c5a065;          /* Dorado */
            --bg-dark: #0e1117;       /* Fondo App */
            --bg-card: #1e1e1e;       /* Fondo Tarjetas */
            --text-main: #ffffff;
            --text-sec: #b0b0b0;
        }

        html, body, [class*="css"] {
            font-family: 'Poppins', sans-serif;
            color: var(--text-main);
        }

        /* --- 2. MENÚ LATERAL (SIDEBAR) --- */
        section[data-testid="stSidebar"] {
            background-color: #111111;
            border-right: 1px solid #333;
        }
        
        div[data-testid="stSidebarNav"] {
            padding-top: 10px;
        }

        /* --- 3. BOTONES NORMALES (3D) --- */
        div.stButton > button {
            background: linear-gradient(145deg, var(--primary), #3a080a);
            color: var(--gold) !important;
            border: 1px solid var(--primary);
            border-radius: 8px;
            padding: 0.5rem 1rem;
            font-weight: 600;
            letter-spacing: 0.5px;
            transition: all 0.2s ease;
            box-shadow: 0 4px 0 #2a0506, 0 5px 10px rgba(0,0,0,0.2); /* Sombra dura 3D */
            width: 100%;
        }

        div.stButton > button:hover {
            transform: translateY(-2px);
            background: linear-gradient(145deg, var(--primary-hover), var(--primary));
            box-shadow: 0 6px 0 #2a0506, 0 10px 15px rgba(197, 160, 101, 0.1);
            border-color: var(--gold);
        }

        div.stButton > button:active {
            transform: translateY(4px);
            box-shadow: 0 0 0 #2a0506;
        }
        
        /* Botones Secundarios (Gris/Transparente) */
        button[kind="secondary"] {
            background: transparent !important;
            border: 1px solid #444 !important;
            color: #aaa !important;
            box-shadow: none !important;
        }

        /* --- 4. BOTONES TIPO TARJETA (DASHBOARD INICIO) --- */
        /* Esta clase se usa para los botones grandes del menú principal */
        div.stButton > button.dashboard-btn {
            height: 140px !important;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            background: var(--bg-card) !important;
            border: 1px solid #333 !important;
            border-left: 5px solid var(--primary) !important;
            box-shadow: 0 4px 10px rgba(0,0,0,0.3) !important;
            white-space: pre-wrap !important;
            margin-bottom: 10px;
        }

        div.stButton > button.dashboard-btn:hover {
            border-color: var(--gold) !important;
            border-left: 5px solid var(--gold) !important;
            transform: translateY(-5px) !important;
            box-shadow: 0 10px 20px rgba(0,0,0,0.5) !important;
        }
        
        div.stButton > button.dashboard-btn p {
            font-size: 1.1rem !important;
            color: var(--text-main) !important;
        }

        /* --- 5. TARJETAS DE MÉTRICAS (KPIs) --- */
        div[data-testid="stMetric"] {
            background-color: var(--bg-card);
            border-radius: 10px;
            padding: 15px;
            border: 1px solid #333;
            border-left: 4px solid var(--gold);
            box-shadow: 2px 2px 10px rgba(0,0,0,0.2);
        }
        div[data-testid="stMetricLabel"] { color: var(--text-sec); font-size: 0.9rem; }
        div[data-testid="stMetricValue"] { color: var(--text-main); font-weight: 700; }

        /* --- 6. TABLAS (DATAFRAMES) --- */
        div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {
            border: 1px solid #333;
            border-radius: 10px;
            background-color: var(--bg-card);
        }

        /* --- 7. ELEMENTOS DE FORMULARIO --- */
        div[data-baseweb="select"] > div, div[data-baseweb="input"] > div {
            background-color: #2b2b2b !important;
            border-color: #444 !important;
            color: white !important;
            border-radius: 8px !important;
        }

        /* Ocultar footer de Streamlit */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
    </style>
    """, unsafe_allow_html=True)