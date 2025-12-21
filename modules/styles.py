import streamlit as st

def cargar_estilos():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Poppins', sans-serif;
        }

        /* --- SIDEBAR PREMIUM --- */
        [data-testid="stSidebar"] {
            background-color: #f8f9fa;
        }
        
        .nav-link {
            border-radius: 12px !important;
            margin: 3px 0px !important;
        }

        .nav-link-selected {
            background-color: #580f12 !important;
            color: white !important;
            border: 2px solid #c5a065 !important;
            border-radius: 12px !important;
        }

        /* --- TARJETAS DEL INICIO --- */
        .card-modulo {
            background-color: white;
            border: 2px solid #c5a065;
            border-radius: 20px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08);
            transition: all 0.3s ease;
            margin-bottom: 10px;
            min-height: 180px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        }

        .card-modulo:hover {
            transform: translateY(-5px);
            box-shadow: 0 12px 25px rgba(197, 160, 101, 0.3);
            border-color: #580f12;
        }

        .card-modulo h3 {
            color: #580f12;
            margin: 10px 0 5px 0;
            font-size: 1.1rem;
            font-weight: 700;
        }

        .card-modulo p {
            color: #666;
            font-size: 0.8rem;
            margin: 0;
        }

        /* --- BOTONES --- */
        div.stButton > button {
            border-radius: 10px;
            text-transform: uppercase;
            font-size: 0.8rem;
            font-weight: 600;
            transition: 0.2s;
        }

        /* --- LIMPIEZA --- */
        header {visibility: hidden;}
        footer {visibility: hidden;}
        
        /* Contenedor de retorno */
        .btn-volver {
            margin-bottom: 20px;
        }
    </style>
    """, unsafe_allow_html=True)
