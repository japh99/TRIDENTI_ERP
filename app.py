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

# --- GESTOR DE COOKIES (CORREGIDO: SIN CACHÉ) ---
# Hemos eliminado @st.cache_resource para quitar el cuadro amarillo
def get_manager():
    return stx.CookieManager()

cookie_manager = get_manager()

# --- ESTADO DE NAVEGACIÓN ---
if "menu_index" not in st.session_state:
    st.session_state["menu_index"] = 0

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
            st.markdown("<h1 style='text-align: center; color: #c5a065;'>🔱 TRIDENTI</h1>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: #888;'>Sistema de Gestión Integral V7</p>", unsafe_allow_html=True)
            st.markdown("---")
            usuario = st.selectbox("Perfil", ["Seleccionar...", "Gerencia (Admin)", "Operación (Cocina)"])
            password = st.text_input("Contraseña", type="password")
            if st.button("🔓 INGRESAR", type="primary", use_container_width=True):
                user_key = "admin" if "Gerencia" in usuario else "cocina"
                if usuario != "Seleccionar..." and password == USUARIOS.get(user_key):
                    st.session_state["usuario_valido"] = True
                    st.session_state["rol_actual"] = usuario
                    # Cookie dura 7 días
                    cookie_manager.set("tridenti_user", usuario, expires_at=datetime.now() + timedelta(days=7))
                    registrar_acceso(sheet, usuario, user_key)
                    st.rerun()
                else: st.error("Error de credenciales")

# --- DASHBOARD HOME ---
def show_dashboard_home():
    st.markdown(f"## 👋 Bienvenido, {st.session_state['rol_actual'].split(' ')[0]}")
    st.markdown("---")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        with st.container(border=True):
            st.markdown("### 💡 Inteligencia")
            st.caption("KPIs y Análisis")
            if st.button("Ir a Inteligencia", use_container_width=True): ir_a(1)
    
    with col2:
        with st.container(border=True):
            st.markdown("### 🚀 Estrategia")
            st.caption("Matriz BCG")
            if st.button("Ir a Matriz BCG", use_container_width=True): ir_a(2)

    with col3:
        with st.container(border=True):
            st.markdown("### 🏦 Financiero")
            st.caption("Gastos Fijos")
            if st.button("Ir a Financiero", use_container_width=True): ir_a(3)

    with col4:
        with st.container(border=True):
            st.markdown("### 🔐 Tesorería")
            st.caption("Cierre de Caja")
            if st.button("Ir a Tesorería", use_container_width=True): ir_a(4)

    st.write("")

    c5, c6, c7, c8 = st.columns(4)

    with c5:
        with st.container(border=True):
            st.markdown("### 📉 Ventas")
            st.caption("Historial Diario")
            if st.button("Ir a Ventas", use_container_width=True): ir_a(5)

    with c6:
        with st.container(border=True):
            st.markdown("### 📦 Inventario")
            st.caption("Kardex y Explosión")
            if st.button("Ir a Inventario", use_container_width=True): ir_a(6)

    with c7:
        with st.container(border=True):
            st.markdown("### 🛒 Compras")
            st.caption("Facturas Prov.")
            if st.button("Ir a Compras", use_container_width=True): ir_a(8)

    with c8:
        with st.container(border=True):
            st.markdown("### 👨‍🍳 Recetas")
            st.caption("Fichas Técnicas")
            if st.button("Ir a Recetas", use_container_width=True): ir_a(12)

def main():
    styles.cargar_estilos()
    
    sheet = conectar_google_sheets()
    if not sheet: st.error("Error BD"); return

    # Login Logic
    if "usuario_valido" not in st.session_state: st.session_state["usuario_valido"] = False
    
    # Intento de auto-login por cookie
    if not st.session_state["usuario_valido"]:
        try:
            cookie = cookie_manager.get("tridenti_user")
            if cookie:
                st.session_state["usuario_valido"] = True
                st.session_state["rol_actual"] = cookie
                time.sleep(0.1); st.rerun()
        except: pass
    
    if not st.session_state["usuario_valido"]:
        login_form(sheet)
        return

    # --- SISTEMA ---
    rol = st.session_state["rol_actual"]
    nombre_app = "TRIDENTI V7"
    
    try:
        df_c = leer_datos_seguro(sheet.worksheet("DB_CONFIG"))
        if not df_c.empty:
            conf = dict(zip(df_c['Parametro'], df_c['Valor']))
            if "EMPRESA_NOMBRE" in conf: nombre_app = conf["EMPRESA_NOMBRE"]
    except: pass

    with st.sidebar:
        st.title(nombre_app)
        
        if rol == "Gerencia (Admin)":
            opciones = [
                "Inicio",           # 0
                "Inteligencia",     # 1
                "Matriz BCG",       # 2
                "Financiero",       # 3
                "Tesoreria",        # 4
                "Ventas",           # 5
                "Inventario",       # 6
                "Sugeridos",        # 7
                "Compras",          # 8
                "Gastos",           # 9
                "Insumos",          # 10
                "Sub-Recetas",      # 11
                "Recetas",          # 12
                "Activos",          # 13
                "Proveedores",      # 14
                "Auditoría",        # 15
                "Reportar Daño",    # 16
                "Configuración"     # 17
            ]
            iconos = [
                "house", "lightbulb", "stars", "bank", "safe",
                "graph-up-arrow", "clipboard-data", "cart-check", "cart4", "wallet2",
                "box-seam", "fire", "journal-text", "tools", "people",
                "check-circle", "exclamation-triangle", "gear"
            ]
            
            selected = option_menu(
                menu_title="Panel de Control",
                options=opciones,
                icons=iconos,
                menu_icon="list",
                default_index=st.session_state["menu_index"],
                styles={"nav-link-selected": {"background-color": "#580f12"}}
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

    # --- ROUTER ---
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
