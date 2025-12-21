import streamlit as st

def cargar_estilos():
    st.markdown("""
    <style>
        /* --- FUENTES --- */
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Poppins', sans-serif;
        }

        /* --- 1. BARRA LATERAL (SIDEBAR) ESTILO PREMIUM --- */
        /* Estilo para los ítems del menú lateral */
        [data-testid="stSidebarNav"] ul {
            padding-left: 1rem;
            padding-right: 1rem;
        }

        [data-testid="stSidebarNav"] ul li {
            border-radius: 15px;
            margin-bottom: 8px;
            transition: all 0.3s ease;
        }

        /* Ítem seleccionado (El efecto guinda con borde dorado) */
        [data-testid="stSidebarNav"] ul li a[aria-current="page"] {
            background-color: #580f12 !important; /* Guinda Tridenti */
            color: white !important;
            border: 2px solid #c5a065 !important; /* Borde Dorado */
            border-radius: 15px !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
        }
        
        /* Iconos del menú en blanco cuando está seleccionado */
        [data-testid="stSidebarNav"] ul li a[aria-current="page"] span {
            color: white !important;
        }

        /* Hover en el menú lateral */
        [data-testid="stSidebarNav"] ul li:hover {
            background-color: rgba(197, 160, 101, 0.1);
            transform: translateX(5px);
        }

        /* --- 2. TARJETAS DE INICIO (DASHBOARD CARDS) --- */
        /* Si usas contenedores para el inicio, usa esta clase personalizada */
        .inicio-card {
            background-color: white;
            border-radius: 20px;
            padding: 25px;
            border: 2px solid #c5a065; /* Borde Dorado */
            box-shadow: 0 10px 25px rgba(0,0,0,0.1);
            text-align: center;
            transition: all 0.3s ease;
            margin-bottom: 20px;
        }
        
        .inicio-card:hover {
            transform: scale(1.03);
            box-shadow: 0 15px 35px rgba(197, 160, 101, 0.3);
        }

        /* --- 3. MÉTRICAS (Métricas 3D mejoradas) --- */
        div[data-testid="stMetric"] {
            background-color: #ffffff;
            border: 2px solid #c5a065; /* Borde Dorado */
            border-radius: 20px !important;
            padding: 20px !important;
            box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
            transition: all 0.3s ease;
        }
        
        div[data-testid="stMetric"]:hover {
            transform: translateY(-5px);
            border-color: #580f12; /* Cambia a guinda al pasar el mouse */
        }

        div[data-testid="stMetricLabel"] { font-size: 1rem; font-weight: 600; color: #333; }
        div[data-testid="stMetricValue"] { font-size: 1.8rem; font-weight: 700; color: #580f12; }

        /* --- 4. BOTONES TIPO PIANO (3D) --- */
        div.stButton > button {
            width: 100%;
            background-color: #ffffff;
            color: #580f12;
            border: 2px solid #c5a065;
            border-bottom: 6px solid #c5a065;
            border-radius: 15px;
            padding: 0.8rem 1rem;
            font-weight: 700;
            transition: all 0.1s;
        }

        button[kind="primary"] {
            background-color: #580f12 !important;
            color: white !important;
            border: 2px solid #c5a065 !important;
            border-bottom: 6px solid #8e6d3d !important;
        }

        div.stButton > button:active {
            border-bottom: 2px solid;
            transform: translateY(4px);
        }

        /* --- 5. TABLAS Y DF --- */
        div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {
            border: 2px solid #c5a065;
            border-radius: 15px;
            overflow: hidden;
        }

        /* Limpieza Visual */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        /* Sidebar background */
        [data-testid="stSidebar"] {
            background-color: #f8f9fa;
            border-right: 1px solid #e0e0e0;
        }
    </style>
    """, unsafe_allow_html=True)
