import streamlit as st

def cargar_estilos():
    st.markdown("""
    <style>
        /* --- FUENTES --- */
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap');

        :root {
            --primary: #580f12;       /* Vino Tinto */
            --gold: #c5a065;          /* Dorado */
            --bg-dark: #0e1117;       /* Fondo App */
            --bg-card: #1c1c1e;       /* Fondo Tarjetas */
            --text: #ffffff;
        }

        html, body, [class*="css"] {
            font-family: 'Poppins', sans-serif;
            color: var(--text);
            background-color: var(--bg-dark);
        }

        /* --- SIDEBAR --- */
        section[data-testid="stSidebar"] {
            background-color: #111;
            border-right: 1px solid #333;
        }

        /* --- BOTONES TARJETA (DASHBOARD) --- */
        div.stButton > button {
            background-color: var(--bg-card);
            color: white;
            border: 1px solid #333;
            border-radius: 12px;
            padding: 15px;
            transition: all 0.3s ease;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            text-align: center;
            height: 100%;
            width: 100%;
        }

        div.stButton > button:hover {
            border-color: var(--gold);
            transform: translateY(-5px);
            box-shadow: 0 8px 15px rgba(197, 160, 101, 0.2);
            background-color: #252525;
            color: var(--gold);
        }

        /* --- CLASES DE COLOR PARA TEXTOS --- */
        .gold-text { color: #c5a065 !important; font-weight: bold; }
        .red-text { color: #D93838 !important; font-weight: bold; }
        .blue-text { color: #4A90E2 !important; font-weight: bold; }
        
        h1, h2, h3 { color: white !important; }
        p, span { color: #aaa; }

        /* --- OCULTAR ELEMENTOS NATIVOS --- */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)
