import streamlit as st

def cargar_estilos():
    st.markdown("""
    <style>
        /* --- 1. FUENTES --- */
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');

        :root {
            --primary: #580f12;       /* Vino Tinto Tridenti */
            --gold: #c5a065;          /* Dorado */
            --bg-app: #f8f9fa;        /* Gris Perla Muy Claro (Fondo) */
            --bg-card: #ffffff;       /* Blanco Puro (Tarjetas) */
            --text-main: #2c3e50;     /* Azul Oscuro Casi Negro (Texto Principal) */
            --text-light: #6c757d;    /* Gris (Subtítulos) */
        }

        html, body, [class*="css"] {
            font-family: 'Poppins', sans-serif;
            color: var(--text-main);
            background-color: var(--bg-app);
        }

        /* --- 2. FONDO GENERAL --- */
        .stApp {
            background-color: var(--bg-app);
        }

        /* --- 3. MENÚ LATERAL (SIDEBAR) --- */
        section[data-testid="stSidebar"] {
            background-color: #ffffff; /* Blanco */
            border-right: 1px solid #e0e0e0;
            box-shadow: 2px 0 5px rgba(0,0,0,0.05);
        }
        
        div[data-testid="stSidebarNav"] {
            padding-top: 20px;
        }
        
        /* Títulos del sidebar */
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
            color: var(--primary) !important;
        }

        /* --- 4. TÍTULOS Y TEXTOS --- */
        h1, h2, h3 {
            color: var(--primary) !important;
            font-weight: 700 !important;
        }
        
        p, label, span, div {
            color: var(--text-main);
        }
        
        /* Subtítulos pequeños */
        .caption {
            color: var(--text-light) !important;
        }

        /* --- 5. BOTONES TIPO TARJETA (DASHBOARD) --- */
        /* Estos son los botones grandes del inicio */
        div.stButton > button {
            background-color: var(--bg-card) !important;
            color: var(--primary) !important; /* Texto Vino Tinto */
            border: 1px solid #e0e0e0 !important;
            border-left: 5px solid var(--primary) !important; /* Borde Izquierdo Vino */
            border-radius: 12px;
            padding: 15px;
            transition: all 0.3s ease;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05); /* Sombra suave */
            text-align: center;
            height: 100%;
            width: 100%;
            font-weight: 600;
        }

        div.stButton > button:hover {
            transform: translateY(-4px); /* Efecto de elevación */
            box-shadow: 0 10px 15px rgba(88, 15, 18, 0.15); /* Sombra Vino */
            border-color: var(--gold) !important;
            border-left: 5px solid var(--gold) !important;
            color: var(--gold) !important;
        }
        
        div.stButton > button:active {
            background-color: #fce4ec !important; /* Fondo rosado muy suave al clic */
            transform: translateY(0px);
        }

        /* --- 6. BOTONES DE ACCIÓN (Primary) --- */
        /* Botones como "Guardar", "Cerrar Caja" */
        button[kind="primary"] {
            background: linear-gradient(135deg, var(--primary), #8a1c21) !important;
            color: white !important;
            border: none !important;
            box-shadow: 0 4px 6px rgba(88, 15, 18, 0.3) !important;
        }
        button[kind="primary"]:hover {
            box-shadow: 0 6px 12px rgba(88, 15, 18, 0.5) !important;
            transform: scale(1.02);
        }

        /* --- 7. TARJETAS DE MÉTRICAS (KPIs) --- */
        div[data-testid="stMetric"] {
            background-color: var(--bg-card);
            border-radius: 10px;
            padding: 15px;
            border: 1px solid #e0e0e0;
            border-left: 4px solid var(--gold);
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        div[data-testid="stMetricLabel"] { color: var(--text-light); }
        div[data-testid="stMetricValue"] { color: var(--primary); font-size: 1.8rem; }

        /* --- 8. TABLAS --- */
        div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            background-color: white;
        }
        
        /* Encabezados de tabla */
        thead tr th {
            background-color: #f1f3f5 !important;
            color: var(--primary) !important;
            font-weight: bold;
        }

        /* --- 9. INPUTS (Cajas de texto) --- */
        input, select, textarea {
            background-color: white !important;
            color: var(--text-main) !important;
            border: 1px solid #ced4da !important;
            border-radius: 6px;
        }
        
        /* Ocultar adornos de Streamlit */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)
