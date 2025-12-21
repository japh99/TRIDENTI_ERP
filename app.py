import streamlit as st
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
    initial_sidebar_state="collapsed" 
)

# --- CREDENCIALES ---
USUARIOS = {"admin": "1234", "cocina": "0000"}

# --- GESTOR DE COOKIES ---
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
    st.session_state["menu_index"] = 0
    st.rerun()

# --- COMPONENTE VISUAL: TARJETA DORADA ---
def dibujar_card(titulo, desc, emoji, indice):
    st.markdown(f"""
        <div class="card-modulo">
            <div style="font-size: 2.5rem; margin-bottom: 10px;">{emoji}</div>
            <h3 style="margin: 0; font-size: 1.2rem;">{titulo}</h3>
            <p style="margin: 5px 0 15px 0; opacity: 0.8; font-size: 0.85rem;">{desc}</p>
        </div>
    """, unsafe_allow_html=True)
    if st.button(f"Entrar a {titulo}", key=f"btn_home_{indice}", use_container_width=True):
        ir_a(indice)

# --- PANTALLA DE INICIO (DASHBOARD) ---
def show_dashboard_home():
    st.markdown("<h1 style='text-align: center; color: #c5a065;'>🔱 TRIDENTI V7</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Panel de Control Integral</p>", unsafe_allow_html=True)
    st.write("")

    # --- FILA 1: ESTRATEGIA ---
    st.markdown("#### 💰 ESTRATEGIA Y FINANZAS")
    f1 = st.columns(5)
    with f1[0]: dibujar_card("Inteligencia", "KPIs de Negocio", "💡", 1)
    with f1[1]: dibujar_card("Matriz BCG", "Análisis de Platos", "⭐", 2)
    with f1[2]: dibujar_card("Financiero", "Gastos Fijos", "🏛️", 3)
    with f1[3]: dibujar_card("Tesorería", "Cierre de Caja", "🔒", 4)
    with f1[4]: dibujar_card("Banco Profit", "Ahorros Reales", "🐷", 5)

    st.write("")

    # --- FILA 2: OPERACIÓN ---
    st.markdown("#### ⚙️ OPERACIÓN DIARIA")
    f2 = st.columns(5)
    with f2[0]: dibujar_card("Ventas", "Historial Diario", "📈", 6)
    with f2[1]: dibujar_card("Inventario", "Kardex / Stock", "📦", 7)
    with f2[2]: dibujar_card("Sugeridos", "Pedidos Compra", "📝", 8)
    with f2[3]: dibujar_card("Compras", "Facturación", "🛒", 9)
    with f2[4]: dibujar_card("Gastos", "Caja Menor", "💸", 10)

    st.write("")

    # --- FILA 3: INGENIERÍA ---
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
    with f4[3]: st.write("")
    with f4[4]:
        st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)
        # BOTÓN DE CERRAR SESIÓN FUNCIONAL
        if st.button("🔒 CERRAR SESIÓN", type="primary", use_container_width=True, key="logout_home"):
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
                else: st.error("Contraseña incorrecta")

# --- MAIN ---
def main():
    styles.cargar_estilos() # Carga CSS con arreglos para móvil
    sheet = conectar_google_sheets()
    
    if "usuario_valido" not in st.session_state: 
        st.session_state["usuario_valido"] = False
    
    # Auto-login por cookies
    if not st.session_state["usuario_valido"]:
        user_cookie = cookie_manager.get("tridenti_user")
        if user_cookie:
            st.session_state["usuario_valido"] = True
            st.session_state["rol_actual"] = user_cookie
            st.rerun()

    if not st.session_state["usuario_valido"]:
        login_form(sheet)
        return

    # --- ROUTER DE CONTENIDO ---
    idx = st.session_state["menu_index"]

    # BARRA DE NAVEGACIÓN SUPERIOR (BOTÓN VOLVER + BOTÓN ACTUALIZAR)
    if idx != 0:
        c_nav1, c_nav2, c_nav3 = st.columns([1.5, 1, 4])
        if c_nav1.button("⬅️ VOLVER AL PANEL", use_container_width=True):
            ir_a(0)
        if c_nav2.button("🔄 ACTUALIZAR", use_container_width=True):
            st.cache_data.clear() # Limpia caché antes de recargar
            st.rerun() # Funciona como un F5
        st.markdown("---")

    # Módulos según índice
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
