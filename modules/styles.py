import streamlit as st

def cargar_estilos():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');

        html, body, [data-testid="stAppViewContainer"] {
            font-family: 'Poppins', sans-serif;
        }

        /* --- FORZAR OCULTAR BARRA LATERAL --- */
        [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {
            display: none !important;
        }

        /* --- VARIABLES DE COLOR ADAPTATIVAS (MEJORADO PARA MÓVIL) --- */
        :root {
            --bg-global: #ffffff;
            --card-bg: #ffffff;
            --card-text: #333333;
            --card-shadow: rgba(0, 0, 0, 0.1);
        }

        @media (prefers-color-scheme: dark) {
            :root {
                --bg-global: #0e1117; /* Fondo estándar dark de Streamlit */
                --card-bg: #1e1e1e;
                --card-text: #f8f9fa;
                --card-shadow: rgba(0, 0, 0, 0.5);
            }
            /* Forzar el fondo de la app en móviles */
            [data-testid="stAppViewContainer"] {
                background-color: var(--bg-global) !important;
            }
        }

        /* --- TARJETAS DE MÉTRICAS Y MÓDULOS --- */
        div[data-testid="stMetric"], .card-modulo {
            background-color: var(--card-bg) !important;
            color: var(--card-text) !important;
            border: 2px solid #c5a065 !important;
            border-radius: 20px !important;
            box-shadow: 0 8px 16px var(--card-shadow) !important;
            -webkit-box-shadow: 0 8px 16px var(--card-shadow) !important;
        }

        /* Estilo para Botón de Volver y Actualizar (F5) */
        .stButton > button {
            border-radius: 12px !important;
            font-weight: 600 !important;
            transition: 0.3s;
        }

        /* --- LIMPIEZA --- */
        header, footer { visibility: hidden !important; }
    </style>
    """, unsafe_allow_html=True)
