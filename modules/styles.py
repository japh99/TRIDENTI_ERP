import streamlit as st

def cargar_estilos():
    st.markdown("""
    <style>
        /* --- 1. FUENTES --- */
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');

        :root {
            --bg-app: #fdf0d5;        /* Fondo Crema */
            --primary: #780000;       /* Vino Tinto */
            --accent: #c1121f;        /* Rojo Vivo */
            --secondary: #003049;     /* Azul Prusiano */
            --text-main: #000000;     /* NEGRO PURO (Para lectura) */
            --bg-card: #ffffff;       /* Blanco */
        }

        /* --- 2. FORZADO DE MODO CLARO (CRÍTICO PARA MÓVIL) --- */
        
        /* Esto obliga a que TODO el texto sea oscuro, ignorando el modo noche del iPhone/Android */
        html, body, [class*="css"], .stMarkdown, .stText, p, div, span, label, h1, h2, h3, h4, h5, h6 {
            font-family: 'Poppins', sans-serif;
            color: var(--text-main) !important;
            background-color: transparent; /* Evita parches negros */
        }

        /* Fondo de la App */
        .stApp {
            background-color: var(--bg-app) !important;
        }

        /* --- 3. BARRA LATERAL (SIDEBAR) --- */
        section[data-testid="stSidebar"] {
            background-color: var(--bg-card) !important;
            border-right: 2px solid var(--secondary);
        }
        
        /* Textos del Sidebar específicamente */
        section[data-testid="stSidebar"] p, 
        section[data-testid="stSidebar"] span,
        section[data-testid="stSidebar"] div {
            color: var(--secondary) !important;
        }

        /* --- 4. TÍTULOS DE COLOR --- */
        /* Sobreescribimos el color negro solo para títulos grandes */
        h1, h2, h3 {
            color: var(--primary) !important;
            font-weight: 800 !important;
        }
        h4, h5 {
            color: var(--secondary) !important;
        }

        /* --- 5. TARJETAS DEL DASHBOARD --- */
        div.stButton > button {
            background-color: var(--bg-card) !important;
            color: var(--secondary) !important; /* Texto Azul */
            border: 2px solid var(--secondary) !important;
            border-left: 6px solid var(--primary) !important;
            border-radius: 12px;
            padding: 15px;
            box-shadow: 0 4px 6px rgba(0, 48, 73, 0.1);
            font-weight: 700 !important;
        }

        div.stButton > button:hover {
            transform: translateY(-3px);
            background-color: var(--primary) !important;
            color: #fdf0d5 !important; /* Texto claro al pasar mouse */
            border-color: var(--primary) !important;
        }
        
        div.stButton > button p {
            color: inherit !important; /* Heredar color del botón */
        }

        /* --- 6. BOTONES PRIMARIOS (ACCIONES) --- */
        button[kind="primary"] {
            background: linear-gradient(135deg, var(--primary), var(--accent)) !important;
            color: #ffffff !important; /* Blanco solo para botones de acción */
            border: none !important;
            box-shadow: 0 4px 0 var(--secondary) !important;
        }
        
        /* Corrección de texto dentro de botones primarios */
        button[kind="primary"] p {
            color: #ffffff !important;
        }

        /* --- 7. INPUTS (CAJAS DE TEXTO) --- */
        /* Fondo blanco y letra negra obligatoria */
        input, textarea, select {
            background-color: #ffffff !important;
            color: #000000 !important;
            border: 1px solid var(--secondary) !important;
        }
        
        /* El texto dentro de los selectbox también */
        div[data-baseweb="select"] span {
            color: #000000 !important;
        }

        /* --- 8. TABLAS --- */
        div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {
            background-color: white !important;
            border: 2px solid var(--secondary);
            border-radius: 10px;
        }
        
        thead tr th {
            background-color: var(--secondary) !important;
            color: #ffffff !important;
        }
        
        tbody td {
            color: #000000 !important;
            background-color: #ffffff !important;
        }

        /* --- 9. MENSAJES (Alertas) --- */
        .stAlert {
            color: #000000 !important;
        }

        /* Ocultar footer */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)
