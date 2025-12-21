import streamlit as st
from streamlit_option_menu import option_menu
from datetime import datetime, timedelta
import time
import extra_streamlit_components as stx
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA

# --- IMPORTACIÓN DE MÓDULOS ---
from modules import (
    styles, inteligencia, matriz_bcg, financiero, tesoreria, banco_profit, 
    ventas, inventario, sugerido, compras, gastos, 
    insumos, subrecetas, recetas, activos, proveedores, 
    auditoria_inv, bajas, configuracion
)

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Tridenti ERP V7", 
    page_icon="🔱", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# --- CREDENCIALES ---
USUARIOS = {"admin": "1234", "cocina": "0000"}

# --- GESTOR DE COOKIES ---
@st.cache_resource
def get_cookie_manager():
    return stx.CookieManager()

cookie_manager = get_cookie_manager()

# --- LÓGICA DE NAVEGACIÓN ---
if "menu_index" not in st.session_state: 
    st.session_state["menu_index"] = 0

def ir_a(indice):
    st.session_state["menu_index"] = indice
    st.rerun()

def cerrar_sesion():
    cookie_manager.delete("tridenti_user")
    st.session_state["usuario_valido"] = False
    st.rerun()

# --- COMPONENTE VISUAL: TARJETA DORADA ---
def dibujar_card(titulo, desc, emoji, indice):
    """Genera el cuadro con borde dorado y el botón de entrada."""
    st.markdown(f"""
        <div class="card-modulo">
            <div style="font-size: 2.5rem; margin-bottom: 10px;">{emoji}</div>
            <h3 style="margin: 0; color: #580f12; font-size: 1.2rem;">{titulo}</h3>
            <p style="margin: 5px 0 15px 0; color: #666; font-size: 0.85rem;">{desc}</p>
        </div>
    """, unsafe_allow_html=True)
    if st.button(f"Entrar a {titulo}", key=f"btn_home_{indice}", use_container_width=True):
        ir_a(indice)

# --- PANTALLA DE INICIO (DASHBOARD) ---
def show_dashboard_home():
    st.markdown(f"# 🔱 Panel de Control Principal")
    st.markdown(f"Bienvenido al sistema Tridenti V7. Gestiona tu operación desde aquí.")
    st.write("")

    # --- FILA 1: ESTRATEGIA & FINANZAS ---
    st.markdown("#### 💰 ESTRATEGIA Y FINANZAS")
    f1 = st.columns(5)
    with f1[0]: dibujar_card("Inteligencia", "KPIs de Negocio", "💡", 1)
    with f1[1]: dibujar_card("Matriz BCG", "Análisis de Platos", "⭐", 2)
    with f1[2]: dibujar_card("Financiero", "Gastos Fijos", "🏛️", 3)
    with f1[3]: dibujar_card("Tesorería", "Cierre de Caja", "🔒", 4)
    with f1[4]: dibujar_card("Banco Profit", "Ahorros Reales", "🐷", 5)

    st.write("")

    # --- FILA 2: OPERACIÓN DIARIA ---
    st.markdown("#### ⚙️ OPERACIÓN DIARIA")
    f2 = st.columns(5)
    with f2[0]: dibujar_card("Ventas", "Historial Diario", "📈", 6)
    with f2[1]: dibujar_card("Inventario", "Kardex / Stock", "📦", 7)
    with f2[2]: dibujar_card("Sugeridos", "Pedidos Compra", "📝", 8)
    with f2[3]: dibujar_card("Compras", "Facturación", "🛒", 9)
    with f2[4]: dibujar_card("Gastos", "Caja Menor", "💸", 10)

    st.write("")

    # --- FILA 3: INGENIERÍA DE PRODUCTO ---
    st.markdown("#### 🧠 INGENIERÍA Y CONTROL")
    f3 = st.columns(5)
    with f3[0]: dibujar_card("Insumos", "Maestro Artículos", "🍎", 11)
    with f3[1]: dibujar_card("Sub-Recetas", "Bases y Salsas", "🔥", 12)
    with f3[2]: dibujar_card("Recetas", "Fichas Técnicas", "📖", 13)
    with f3[3]: dibujar_card("Activos", "Mantenimiento", "🛠️", 14)
    with f3[4]: dibujar_card("Proveedores", "Contactos", "🤝", 15)

    st.write("")

    # --- FILA 4: AJUSTES Y SALIDA ---
    st.markdown("#### 🛡️ CONTROL Y AJUSTES")
    f4 = st.columns(5)
    with f4[0]: dibujar_card("Auditoría", "Conteos Inv.", "✅", 16)
    with f4[1]: dibujar_card("Reportar Daño", "Mermas/Bajas", "⚠️", 17)
    with f4[2]: dibujar_card("Configuración", "Ajustes Sistema", "⚙️", 18)
    
    with f4[3]: st.write("") # Espacio vacío

    with f4[4]:
        st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)
        if st.button("🔒 CERRAR SESIÓN", type="primary", use_container_width=True):
            cerrar_sesion()

# --- LOGIN ---
def login_form(sheet):
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("<h1 style='text-align: center; color: #c5a065;'>🔱 TRIDENTI</h1>", unsafe_allow_html=True)
            usuario = st.selectbox("Perfil", ["Seleccionar...", "Gerencia (Admin)", "Operación (Cocina)"])
            password = st.text_input("Contraseña", type="password")
            if st.button("🔓 INGRESAR", type="primary", use_container_width=True):
                user_key = "admin" if "Gerencia" in usuario else "cocina"
                if usuario != "Seleccionar..." and password == USUARIOS.get(user_key):
                    st.session_state["usuario_valido"] = True
                    st.session_state["rol_actual"] = usuario
                    cookie_manager.set("tridenti_user", usuario, expires_at=datetime.now() + timedelta(days=7))
                    st.rerun()
                else: st.error("Credenciales incorrectas")

# --- FUNCIÓN PRINCIPAL (MAIN) ---
def main():
    styles.cargar_estilos()
    sheet = conectar_google_sheets()
    if not sheet: st.error("Error al conectar BD"); return

    # --- GESTIÓN DE SESIÓN ---
    if "usuario_valido" not in st.session_state: 
        st.session_state["usuario_valido"] = False
    
    # Intento de auto-login por cookie
    if not st.session_state["usuario_valido"]:
        user_cookie = cookie_manager.get("tridenti_user")
        if user_cookie:
            st.session_state["usuario_valido"] = True
            st.session_state["rol_actual"] = user_cookie
            st.rerun()

    if not st.session_state["usuario_valido"]:
        login_form(sheet)
        return

    rol = st.session_state["rol_actual"]

    # --- SIDEBAR NAVEGACIÓN ---
    opciones = [
        "Inicio", "Inteligencia", "Matriz BCG", "Financiero", "Tesoreria", "Banco Profit",
        "Ventas", "Inventario", "Sugeridos", "Compras", "Gastos", "Insumos", 
        "Sub-Recetas", "Recetas", "Activos", "Proveedores", "Auditoría", "Reportar Daño", "Configuración"
    ]
    iconos = [
        "house", "lightbulb", "stars", "bank", "safe", "piggy-bank",
        "graph-up-arrow", "clipboard-data", "cart-check", "cart4", "wallet2", "box-seam",
        "fire", "journal-text", "tools", "people", "check-circle", "exclamation-triangle", "gear"
    ]

    with st.sidebar:
        st.markdown(f"<h3 style='color: #580f12;'>🔱 TRIDENTI V7</h3>", unsafe_allow_html=True)
        st.caption(f"Perfil: {rol}")
        
        # Botón para volver al Inicio rápido
        if st.button("🏠 VOLVER AL INICIO", use_container_width=True, type="secondary"):
            ir_a(0)
            
        st.markdown("---")
        
        selected = option_menu(
            menu_title=None, 
            options=opciones, 
            icons=iconos, 
            default_index=st.session_state["menu_index"],
            styles={
                "nav-link-selected": {"background-color": "#580f12"},
                "nav-link": {"font-family": "Poppins, sans-serif", "font-size": "0.9rem"}
            }
        )
        
        # Sincronizar el estado del menú
        new_idx = opciones.index(selected)
        if new_idx != st.session_state["menu_index"]:
            st.session_state["menu_index"] = new_idx
            st.rerun()
        
        st.markdown("---")
        if st.button("🔒 CERRAR SESIÓN"):
            cerrar_sesion()

    # --- ROUTER DE CONTENIDO ---
    idx = st.session_state["menu_index"]

    # SI NO ESTOY EN INICIO, MOSTRAR BOTÓN DE REGRESO RÁPIDO
    if idx != 0:
        c_back1, c_back2 = st.columns([1, 4])
        if c_back1.button("⬅️ REGRESAR AL PANEL"):
            ir_a(0)
        st.markdown("---")

    # CARGA DE MÓDULOS SEGÚN EL ÍNDICE
    if idx == 0: show_dashboard_home()
    elif idx == 1: inteligencia.show(sheet)
    elif idx == 2: matriz_bcg.show(sheet)
    elif idx == 3: financiero.show(sheet)
    elif idx == 4: tesoreria.show(sheet)
    elif idx == 5: banco_profit.show(sheet)
    elif idx == 6: ventas.show(sheet)
    elif idx == 7: inventario.show(sheet)
    elif idx == 8: sugerido.show(sheet)
    elif idx == 9: compras.show(sheet)
    elif idx == 10: gastos.show(sheet)
    elif idx == 11: insumos.show(sheet)
    elif idx == 12: subrecetas.show(sheet)
    elif idx == 13: recetas.show(sheet)
    elif idx == 14: activos.show(sheet)
    elif idx == 15: proveedores.show(sheet)
    elif idx == 16: auditoria_inv.show(sheet)
    elif idx == 17: bajas.show(sheet)
    elif idx == 18: configuracion.show(sheet)

if __name__ == "__main__":
    main()
