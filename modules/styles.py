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

        /* --- TARJETAS DE MÉTRICAS (TOTALES) - CORRECCIÓN PARA IPAD --- */
        /* Forzamos el contenedor de la métrica */
        div[data-testid="stMetric"] {
            background-color: white !important;
            border: 2px solid #c5a065 !important;
            border-radius: 20px !important;
            padding: 20px !important;
            box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1) !important;
            -webkit-box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1) !important; /* Para iPad */
            display: block !important;
            width: 100% !important;
        }

        /* Texto dentro de las métricas */
        div[data-testid="stMetricLabel"] > div {
            font-size: 1rem !important;
            font-weight: 600 !important;
            color: #333 !important;
        }
        
        div[data-testid="stMetricValue"] > div {
            font-size: 1.8rem !important;
            font-weight: 700 !important;
            color: #580f12 !important;
        }

        /* --- TARJETAS DEL INICIO (DASHBOARD CARDS) --- */
        .card-modulo {
            background-color: white !important;
            border: 2px solid #c5a065 !important;
            border-radius: 20px !important;
            padding: 20px !important;
            text-align: center !important;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08) !important;
            -webkit-box-shadow: 0 4px 15px rgba(0,0,0,0.08) !important;
            margin-bottom: 10px !important;
            min-height: 180px !important;
            display: flex !important;
            flex-direction: column !important;
            justify-content: center !important;
            align-items: center !important;
        }

        /* --- BOTONES 3D --- */
        div.stButton > button {
            border-radius: 12px !important;
            border: 1px solid #c5a065 !important;
            border-bottom: 5px solid #c5a065 !important;
            background-color: white !important;
            color: #580f12 !important;
            font-weight: 700 !important;
            -webkit-appearance: none !important; /* Quita estilo nativo de iOS */
        }

        button[kind="primary"] {
            background-color: #580f12 !important;
            color: white !important;
            border-bottom: 5px solid #3a080a !important;
        }

        /* --- LIMPIEZA GENERAL --- */
        header, footer { visibility: hidden !important; }
        
        /* Ajuste para que en iPad no se amontonen las columnas */
        @media (max-width: 991px) {
            div[data-testid="stMetric"] {
                margin-bottom: 15px !important;
            }
        }
    </style>
    """, unsafe_allow_html=True)
