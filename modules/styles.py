import streamlit as st

def cargar_estilos():
    st.markdown("""
    <style>
        /* --- FUENTES --- */
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Poppins', sans-serif;
        }

        /* --- 1. TARJETAS DE INFORMACIÓN (Métricas 3D) --- */
        div[data-testid="stMetric"] {
            background-color: rgba(255, 255, 255, 0.05); /* Fondo sutil translúcido */
            border: 1px solid rgba(128, 128, 128, 0.2);
            border-left: 6px solid #c5a065; /* Acento Dorado Tridenti */
            border-radius: 15px; /* Bordes muy redondos */
            padding: 15px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1), 0 1px 3px rgba(0, 0, 0, 0.08); /* Sombra suave */
            transition: transform 0.2s ease;
        }
        
        div[data-testid="stMetric"]:hover {
            transform: translateY(-2px); /* Se levanta un poco */
            box-shadow: 0 10px 20px rgba(0, 0, 0, 0.15); /* Sombra más fuerte */
            border-color: #c5a065;
        }

        /* Texto de las métricas */
        div[data-testid="stMetricLabel"] { font-size: 0.9rem; font-weight: 600; opacity: 0.8; }
        div[data-testid="stMetricValue"] { font-size: 2rem; font-weight: 700; color: #D93838; /* Rojo Tridenti */ }

        /* --- 2. BOTONES 3D REALES --- */
        div.stButton > button {
            background-color: #ffffff;
            color: #333333;
            border: 1px solid #cccccc;
            border-bottom: 5px solid #aaaaaa; /* EL EFECTO 3D ES ESTE BORDE */
            border-radius: 12px;
            padding: 0.5rem 1rem;
            font-weight: 700;
            transition: all 0.1s;
        }

        /* Botón Primario (Rojo) */
        button[kind="primary"] {
            background-color: #580f12 !important;
            color: white !important;
            border: 1px solid #3a080a !important;
            border-bottom: 5px solid #2a0506 !important; /* Piso oscuro */
        }

        /* Efecto al presionar (Hundir) */
        div.stButton > button:active {
            border-bottom: 1px solid; /* Se quita el piso */
            transform: translateY(4px); /* Se mueve hacia abajo */
        }
        
        /* Hover */
        div.stButton > button:hover {
            border-color: #c5a065 !important; /* Brillo dorado */
        }

        /* --- 3. CONTENEDORES Y TABLAS --- */
        /* Bordes redondeados para tablas */
        div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {
            border: 1px solid rgba(128, 128, 128, 0.3);
            border-radius: 12px;
            overflow: hidden; /* Para que las esquinas no se salgan */
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }

        /* Tarjetas generales (st.container con borde) */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 15px;
            border: 1px solid rgba(128, 128, 128, 0.2);
            box-shadow: 0 4px 10px rgba(0,0,0,0.05);
        }

        /* --- 4. EXPANDERS (Acordeones) --- */
        .streamlit-expanderHeader {
            font-weight: 600;
            border-radius: 8px;
            background-color: rgba(128, 128, 128, 0.05);
        }

        /* Limpieza Visual */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)
