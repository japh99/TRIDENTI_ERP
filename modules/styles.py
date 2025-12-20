import streamlit as st

def cargar_estilos():
    st.markdown("""
    <style>
        /* --- 1. FUENTES --- */
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');

        :root {
            --bg-app: #fdf0d5;        /* Fondo Crema */
            --primary: #780000;       /* Vino Tinto (Botones/Títulos) */
            --accent: #c1121f;        /* Rojo Vivo (Hover/Alertas) */
            --secondary: #003049;     /* Azul Prusiano (Texto fuerte/Bordes) */
            --text-main: #000000;     /* Negro (Texto lectura) */
            --bg-card: #ffffff;       /* Blanco (Tarjetas) */
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

        /* --- 3. BARRA LATERAL (SIDEBAR) --- */
        section[data-testid="stSidebar"] {
            background-color: var(--bg-card) !important; /* Blanco para contraste */
            border-right: 2px solid var(--secondary); /* Borde Azul Prusiano */
        }
        
        /* Títulos del sidebar */
        [data-testid="stSidebar"] h1 {
            color: var(--primary) !important;
            text-shadow: 1px 1px 0px rgba(0,0,0,0.1);
        }
        [data-testid="stSidebar"] p, [data-testid="stSidebar"] span {
            color: var(--secondary) !important;
            font-weight: 500;
        }

        /* --- 4. TÍTULOS --- */
        h1, h2, h3 {
            color: var(--primary) !important; /* Vino Tinto */
            font-weight: 800 !important;
        }
        h4, h5, h6 {
            color: var(--secondary) !important; /* Azul Prusiano */
        }

        /* --- 5. BOTONES TIPO TARJETA (DASHBOARD) --- */
        div.stButton > button {
            background-color: var(--bg-card) !important;
            color: var(--secondary) !important; /* Texto Azul */
            border: 1px solid var(--secondary) !important;
            border-left: 6px solid var(--primary) !important; /* Borde Izq Vino */
            border-radius: 12px;
            padding: 15px;
            transition: all 0.3s ease;
            box-shadow: 0 4px 6px rgba(0, 48, 73, 0.1);
            text-align: center;
            height: 100%;
            width: 100%;
            font-weight: 700;
        }

        div.stButton > button:hover {
            transform: translateY(-4px);
            background-color: var(--primary) !important; /* Fondo Vino al pasar mouse */
            color: #fdf0d5 !important; /* Texto Crema */
            border-color: var(--primary) !important;
            box-shadow: 0 8px 15px rgba(120, 0, 0, 0.3);
        }
        
        div.stButton > button:active {
            background-color: var(--accent) !important; /* Rojo vivo al clic */
        }

        /* --- 6. BOTONES DE ACCIÓN (PRIMARY) --- */
        /* Botones como "Guardar", "Cerrar Caja" */
        button[kind="primary"] {
            background: linear-gradient(135deg, var(--primary), var(--accent)) !important;
            color: #ffffff !important;
            border: none !important;
            border-radius: 8px !important;
            box-shadow: 0 4px 0 var(--secondary) !important; /* Sombra dura Azul */
        }
        button[kind="primary"]:hover {
            transform: scale(1.02);
            box-shadow: 0 6px 0 var(--secondary) !important;
        }

        /* --- 7. TARJETAS DE MÉTRICAS (KPIs) --- */
        div[data-testid="stMetric"] {
            background-color: var(--bg-card);
            border: 1px solid rgba(0, 48, 73, 0.1);
            border-radius: 10px;
            padding: 15px;
            border-left: 5px solid var(--secondary); /* Borde Azul */
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        }
        div[data-testid="stMetricLabel"] { color: var(--secondary) !important; font-weight: 600; }
        div[data-testid="stMetricValue"] { color: var(--primary) !important; font-size: 1.8rem; }

        /* --- 8. TABLAS (DATAFRAMES) --- */
        div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {
            border: 2px solid var(--secondary);
            border-radius: 8px;
            background-color: white;
            box-shadow: 4px 4px 0px rgba(0, 48, 73, 0.1);
        }
        
        /* Encabezados de tabla */
        thead tr th {
            background-color: var(--secondary) !important;
            color: #ffffff !important; /* Texto Blanco */
            font-weight: bold;
        }
        
        /* Filas */
        tbody tr:nth-child(even) {
            background-color: #f8f9fa;
        }

        /* --- 9. INPUTS --- */
        input, select, textarea {
            background-color: #ffffff !important;
            color: var(--text-main) !important;
            border: 1px solid var(--secondary) !important;
            border-radius: 6px;
        }
        
        /* Focus en Inputs */
        div[data-baseweb="input"]:focus-within {
            border-color: var(--accent) !important;
            box-shadow: 0 0 0 2px rgba(193, 18, 31, 0.2) !important;
        }

        /* Ocultar adornos de Streamlit */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)
