import streamlit as st

def cargar_estilos():
    st.markdown("""
    <style>
        /* --- 1. FUENTES --- */
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');

        :root {
            --primary: #580f12;       /* Vino Tinto */
            --gold: #c5a065;          /* Dorado */
            --bg-app: #f9f7f2;        /* BEIGE CREMA SUAVE (Tu pedido) */
            --bg-sidebar: #ffffff;    /* Blanco para la barra */
            --bg-card: #ffffff;       /* Blanco para tarjetas */
            --text-main: #2c1810;     /* Café muy oscuro (Casi negro) para leer bien */
            --text-light: #5d4037;    /* Café suave para subtítulos */
        }

        html, body, [class*="css"] {
            font-family: 'Poppins', sans-serif;
            color: var(--text-main) !important;
            background-color: var(--bg-app) !important;
        }

        /* --- 2. FONDO GENERAL --- */
        .stApp {
            background-color: var(--bg-app) !important;
        }

        /* --- 3. BARRA LATERAL (SIDEBAR) CLARA --- */
        section[data-testid="stSidebar"] {
            background-color: var(--bg-sidebar) !important;
            border-right: 1px solid #e0e0e0;
            box-shadow: 2px 0 10px rgba(0,0,0,0.05);
        }
        
        div[data-testid="stSidebarNav"] {
            padding-top: 20px;
        }

        /* Textos del sidebar */
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
            color: var(--primary) !important;
        }
        [data-testid="stSidebar"] p, [data-testid="stSidebar"] span {
            color: var(--text-main) !important;
        }

        /* --- 4. BOTONES TIPO TARJETA (DASHBOARD) --- */
        div.stButton > button {
            background-color: var(--bg-card) !important;
            color: var(--primary) !important;
            border: 1px solid #d7ccc8 !important; /* Borde beige oscuro */
            border-left: 5px solid var(--primary) !important;
            border-radius: 12px;
            padding: 15px;
            transition: all 0.3s ease;
            box-shadow: 0 4px 6px rgba(44, 24, 16, 0.05);
            text-align: center;
            height: 100%;
            width: 100%;
            font-weight: 600;
        }

        div.stButton > button:hover {
            transform: translateY(-4px);
            box-shadow: 0 10px 15px rgba(88, 15, 18, 0.15);
            border-color: var(--gold) !important;
            border-left: 5px solid var(--gold) !important;
            color: var(--gold) !important;
        }
        
        div.stButton > button:active {
            background-color: #fce4ec !important;
            transform: translateY(0px);
        }

        /* Botones de Acción Primaria (Guardar, Cerrar) */
        button[kind="primary"] {
            background: linear-gradient(135deg, var(--primary), #8a1c21) !important;
            color: white !important;
            border: none !important;
            box-shadow: 0 4px 6px rgba(88, 15, 18, 0.3) !important;
        }

        /* --- 5. TARJETAS DE MÉTRICAS --- */
        div[data-testid="stMetric"] {
            background-color: var(--bg-card);
            border-radius: 10px;
            padding: 15px;
            border: 1px solid #e0e0e0;
            border-left: 4px solid var(--gold);
            box-shadow: 0 2px 4px rgba(44, 24, 16, 0.05);
        }
        div[data-testid="stMetricLabel"] { color: var(--text-light) !important; }
        div[data-testid="stMetricValue"] { color: var(--primary) !important; }

        /* --- 6. TABLAS --- */
        div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            background-color: white;
        }
        
        /* Texto negro en tablas */
        td { color: #000000 !important; }
        th { color: var(--primary) !important; background-color: #f3e9d2 !important; }

        /* --- 7. INPUTS --- */
        input, select, textarea {
            background-color: white !important;
            color: #000000 !important;
            border: 1px solid #ccc !important;
        }

        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)
