import streamlit as st

def cargar_estilos():
    st.markdown("""
    <style>
        /* --- 1. FUENTES --- */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');

        :root {
            --primary: #580f12;       /* Vino Tinto */
            --primary-light: #fdf3f3; /* Fondo rojizo muy suave */
            --gold: #c5a065;          /* Dorado */
            --bg-app: #F5F7F9;        /* Gris Perla (Fondo General) */
            --bg-card: #FFFFFF;       /* Blanco (Tarjetas) */
            --text-main: #1f2937;     /* Gris Oscuro (Casi negro) para lectura */
            --text-light: #6b7280;    /* Gris medio para subtítulos */
            --border: #e5e7eb;        /* Bordes sutiles */
        }

        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
            color: var(--text-main);
            background-color: var(--bg-app);
        }

        /* --- 2. FONDO DE LA APP --- */
        .stApp {
            background-color: var(--bg-app);
        }

        /* --- 3. BARRA LATERAL (SIDEBAR) --- */
        section[data-testid="stSidebar"] {
            background-color: #ffffff;
            border-right: 1px solid #e5e7eb;
            box-shadow: 2px 0 15px rgba(0,0,0,0.02);
        }
        
        div[data-testid="stSidebarNav"] {
            padding-top: 10px;
        }

        /* --- 4. TARJETAS TIPO "SNOWFLAKE" (Tu Imagen) --- */
        /* Aplicamos este estilo a los st.container(border=True) */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background-color: var(--bg-card);
            border: 1px solid #d1d5db;
            border-radius: 8px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
            padding: 20px;
            margin-bottom: 20px;
        }

        /* Header simulado dentro de las tarjetas */
        h3 {
            color: var(--primary) !important;
            font-size: 1.1rem !important;
            font-weight: 700 !important;
            border-bottom: 2px solid var(--gold);
            padding-bottom: 10px;
            margin-bottom: 15px;
            letter-spacing: 0.5px;
        }

        /* --- 5. BOTONES PREMIUM (Estilo Plano Moderno) --- */
        div.stButton > button {
            background-color: white;
            color: var(--primary) !important;
            border: 1px solid var(--primary);
            border-radius: 6px;
            padding: 0.5rem 1rem;
            font-weight: 600;
            transition: all 0.2s ease;
            box-shadow: 0 2px 0 rgba(0,0,0,0.05);
            width: 100%;
        }

        div.stButton > button:hover {
            background-color: var(--primary);
            color: white !important;
            transform: translateY(-1px);
            box-shadow: 0 4px 6px rgba(88, 15, 18, 0.2);
        }

        div.stButton > button:active {
            transform: translateY(1px);
            box-shadow: none;
        }
        
        /* Botón Primario (Acción fuerte) */
        button[type="primary"] {
            background-color: var(--primary) !important;
            color: white !important;
        }

        /* --- 6. TABLAS (DATAFRAMES) - LECTURA PERFECTA --- */
        div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {
            background-color: white;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            overflow: hidden;
        }

        /* Encabezados de tabla */
        thead tr th {
            background-color: #f3f4f6 !important;
            color: #374151 !important;
            font-weight: 600 !important;
            border-bottom: 2px solid #e5e7eb !important;
        }
        
        /* Celdas */
        td {
            color: #111827 !important; /* Negro casi puro para leer bien */
            background-color: white !important;
        }

        /* --- 7. INPUTS (Cajas de texto blancas) --- */
        input, select, textarea {
            background-color: #ffffff !important;
            border: 1px solid #d1d5db !important;
            color: #111827 !important; /* Texto negro */
            border-radius: 6px !important;
        }
        
        div[data-baseweb="select"] > div {
            background-color: #ffffff !important;
            color: #111827 !important;
            border-color: #d1d5db !important;
        }

        /* --- 8. MÉTRICAS (KPIs) --- */
        div[data-testid="stMetric"] {
            background-color: white;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 15px;
            border-left: 5px solid var(--gold);
        }
        div[data-testid="stMetricLabel"] { color: var(--text-light); }
        div[data-testid="stMetricValue"] { color: var(--primary); font-size: 1.8rem; font-weight: 700; }

        /* Ocultar footer */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
    </style>
    """, unsafe_allow_html=True)
