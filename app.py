import streamlit as st
from streamlit_option_menu import option_menu
from datetime import datetime, timedelta
import pytz
import time
import extra_streamlit_components as stx
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA

# --- IMPORTACIÓN DE MÓDULOS ---
from modules import (
    styles,
    inteligencia, matriz_bcg, financiero, tesoreria, ventas, 
    inventario, sugerido, compras, gastos, 
    insumos, subrecetas, recetas, activos, proveedores, 
    auditoria_inv, bajas, configuracion
)

# --- CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Tridenti ERP", page_icon="🔱", layout="wide", initial_sidebar_state="expanded")

# --- CREDENCIALES ---
USUARIOS = {"admin": "1234", "cocina": "0000"}

# --- GESTOR DE COOKIES ---
def get_manager(): return stx.CookieManager()
cookie_manager = get_manager()

# --- NAVEGACIÓN ---
if "menu_index" not in st.session_state: st.session_state["menu_index"] = 0
def ir_a(indice):
    st.session_state["menu_index"] = indice
    st.rerun()

def registrar_acceso(sheet, usuario, rol):
    try:
        try: ws = sheet.worksheet("LOG_ACCESOS")
        except:
            ws = sheet.add_worksheet(title="LOG_ACCESOS", rows="1000", cols="5")
            ws.append_row(["Fecha", "Hora", "Usuario", "Rol", "Status"])
        ahora = datetime.now(ZONA_HORARIA)
        ws.append_row([ahora.strftime("%Y-%m-%d"), ahora.strftime("%H:%M:%S"), usuario, rol, "OK"])
    except: pass

def login_form(sheet):
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("<h1 style='text-align: center; color: #580f12;'>🔱 TRIDENTI</h1>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: #666;'>Sistema de Gestión Integral V7</p>", unsafe_allow_html=True)
            st.markdown("---")
            usuario = st.selectbox("Perfil", ["Seleccionar...", "Gerencia (Admin)", "Operación (Cocina)"])
            password = st.text_input("Contraseña", type="password")
            if st.button("🔓 INGRESAR", type="primary", use_container_width=True):
                user_key = "admin" if "Gerencia" in usuario else "cocina"
                if usuario != "Seleccionar..." and password == USUARIOS.get(user_key):
                    st.session_state["usuario_valido"] = True
                    st.session_state["rol_actual"] = usuario
                    cookie_manager.set("tridenti_user", usuario, expires_at=datetime.now() + timedelta(days=7))
                    registrar_acceso(sheet, usuario, user_key)
                    st.rerun()
                else: st.error("Error de credenciales")

def show_dashboard_home():
    st.markdown(f"## 👋 Bienvenido, {st.session_state['rol_actual'].split(' ')[0]}")
    st.markdown("### Selecciona un módulo:")
    st.write("")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info("💰 **ESTRATEGIA**")
        if st.button("💡 Inteligencia", use_container_width=True): ir_a(1)
        if st.button("🚀 Matriz BCG", use_container_width=True): ir_a(2)
        if st.button("🏦 Financiero", use_container_width=True): ir_a(3)
        if st.button("🔐 Tesorería", use_container_width=True): ir_a(4)

    with col2:
        st.warning("⚙️ **OPERACIÓN**")
        if st.button("📉 Ventas", use_container_width=True): ir_a(5)
        if st.button("📦 Inventario", use_container_width=True): ir_a(6)
        if st.button("🛒 Sugerido", use_container_width=True): ir_a(7)
        if st.button("🛍️ Compras", use_container_width=True): ir_a(8)
        if st.button("💸 Gastos", use_container_width=True): ir_a(9)

    with col3:
        st.success("🧠 **INGENIERÍA**")
        if st.button("📦 Insumos", use_container_width=True): ir_a(10)
        if st.button("🥣 Sub-Recetas", use_container_width=True): ir_a(11)
        if st.button("👨‍🍳 Recetas", use_container_width=True): ir_a(12)
        if st.button("🛠️ Activos", use_container_width=True): ir_a(13)
        if st.button("🤝 Proveedores", use_container_width=True): ir_a(14)
        if st.button("⚙️ Configuración", use_container_width=True): ir_a(17)

    st.markdown("---")
    st.caption("🔱 Tridenti ERP V7.5 - Estable")

def main():
    styles.cargar_estilos()
    
    sheet = conectar_google_sheets()
    if not sheet: st.error("Error BD"); return

    if "usuario_valido" not in st.session_state: st.session_state["usuario_valido"] = False
    if not st.session_state["usuario_valido"]:
        try:
            if cookie_manager.get("tridenti_user"):
                st.session_state["usuario_valido"] = True
                st.session_state["rol_actual"] = cookie_manager.get("tridenti_user")
                time.sleep(0.1); st.rerun()
        except: pass
    
    if not st.session_state["usuario_valido"]:
        login_form(sheet)
        return

    rol = st.session_state["rol_actual"]
    nombre_app = "TRIDENTI V7"
    try:
        df_c = leer_datos_seguro(sheet.worksheet("DB_CONFIG"))
        if not df_c.empty:
            conf = dict(zip(df_c['Parametro'], df_c['Valor']))
            if "EMPRESA_NOMBRE" in conf: nombre_app = conf["EMPRESA_NOMBRE"]
    except: pass

    with st.sidebar:
        if st.button("🏠 INICIO", type="primary", use_container_width=True): ir_a(0)
        st.markdown(f"### {nombre_app}")
        st.caption(f"👤 {rol}")
        
        if rol == "Gerencia (Admin)":
            opciones = [
                "Inicio",
                "Inteligencia", "Matriz BCG", "Financiero", "Tesoreria",
                "Ventas", "Inventario", "Sugeridos", "Compras", "Gastos",
                "Insumos", "Sub-Recetas", "Recetas", "Activos", "Proveedores",
                "Auditoría", "Reportar Daño", "Configuración"
            ]
            iconos = [
                "house",
                "lightbulb", "stars", "bank", "safe",
                "graph-up-arrow", "clipboard-data", "cart-check", "cart4", "wallet2",
                "box-seam", "fire", "journal-text", "tools", "people",
                "check-circle", "exclamation-triangle", "gear"
            ]
            
            # --- AQUÍ ESTÁ EL CAMBIO DE COLORES DEL MENÚ ---
            selected = option_menu(
                menu_title=None,
                options=opciones,
                icons=iconos,
                menu_icon="list",
                default_index=st.session_state["menu_index"],
                styles={
                    "container": {"padding": "0!important", "background-color": "#ffffff"}, # Fondo Blanco
                    "icon": {"color": "#c5a065", "font-size": "14px"}, # Iconos Dorados
                    "nav-link": {
                        "font-size": "14px", 
                        "text-align": "left", 
                        "margin":"0px", 
                        "color": "#2c1810" # Texto Café Oscuro
                    },
                    "nav-link-selected": {"background-color": "#580f12", "color": "white"}, # Selección Vino Tinto
                }
            )
            
            try:
                idx = opciones.index(selected)
                if idx != st.session_state["menu_index"]:
                    st.session_state["menu_index"] = idx
                    st.rerun()
            except: pass
        else:
            opciones = ["Reportar Daño", "Auditoría"]
            selected = option_menu(menu_title=None, options=opciones, icons=["exclamation-triangle", "check-circle"], default_index=0)
        
        st.markdown("---")
        if st.button("🔒 SALIR"):
            cookie_manager.delete("tridenti_user")
            st.session_state["usuario_valido"] = False
            st.rerun()

    if selected != "Inicio" and rol == "Gerencia (Admin)":
        if st.button("⬅️ Volver al Panel"): ir_a(0)

    if selected == "Inicio": show_dashboard_home()
    elif selected == "Inteligencia": inteligencia.show(sheet)
    elif selected == "Matriz BCG": matriz_bcg.show(sheet)
    elif selected == "Financiero": financiero.show(sheet)
    elif selected == "Tesoreria": tesoreria.show(sheet)
    elif selected == "Ventas": ventas.show(sheet)
    elif selected == "Inventario": inventario.show(sheet)
    elif selected == "Sugeridos": sugerido.show(sheet)
    elif selected == "Compras": compras.show(sheet)
    elif selected == "Gastos": gastos.show(sheet)
    elif selected == "Insumos": insumos.show(sheet)
    elif selected == "Sub-Recetas": subrecetas.show(sheet)
    elif selected == "Recetas": recetas.show(sheet)
    elif selected == "Activos": activos.show(sheet)
    elif selected == "Proveedores": proveedores.show(sheet)
    elif selected == "Auditoría": auditoria_inv.show(sheet)
    elif selected == "Reportar Daño": bajas.show(sheet)
    elif selected == "Configuración": configuracion.show(sheet)

if __name__ == "__main__":
    main()
