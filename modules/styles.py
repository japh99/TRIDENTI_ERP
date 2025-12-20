import streamlit as st

def cargar_estilos():
    st.markdown("""
    <style>
        /* --- FUENTES MODERNAS --- */
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap');

        html, body, [class*="css"] {
            font-family: 'Poppins', sans-serif;
        }

        /* --- BOTONES DEL DASHBOARD (TARJETAS) --- */
        /* Hacemos que los botones sean grandes y cuadrados */
        div.stButton > button {
            width: 100%;
            padding: 20px;
            border-radius: 12px;
            font-weight: 600;
            text-align: center;
            transition: transform 0.2s;
            /* Usamos bordes sutiles que funcionan en dark/light */
            border: 1px solid rgba(128, 128, 128, 0.2); 
            background-color: transparent; /* Deja que el tema decida */
        }

        div.stButton > button:hover {
            transform: translateY(-4px);
            border-color: #FF4B4B; /* Color acento nativo de Streamlit */
            box-shadow: 0 4px 10px rgba(0,0,0,0.1);
        }

        /* Texto dentro de los botones grandes */
        div.stButton > button p {
            font-size: 1.1rem;
        }

        /* --- BOTONES DE ACCIÓN (Primary) --- */
        /* Streamlit ya los estiliza bien, solo redondeamos */
        button[kind="primary"] {
            border-radius: 8px;
        }

        /* --- Ocultar menú de desarrollador (Hamburguesa técnica) --- */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
    </style>
    """, unsafe_allow_html=True)
