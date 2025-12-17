import streamlit as st
from streamlit_option_menu import option_menu
from datetime import datetime
import pytz
from utils import conectar_google_sheets, leer_datos_seguro, ZONA_HORARIA

# --- IMPORTACIÓN DE TODOS LOS MÓDULOS ---
from modules import (
    inteligencia, matriz_bcg, tesoreria, ventas, 
    inventario, sugerido, compras, gastos, 
    insumos, recetas, proveedores, 
    auditoria_inv, bajas, configuracion
)

# --- CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Tridenti ERP V7", page_icon="🔱", layout="wide")

# --- CREDENCIALES DE ACCESO ---
USUARIOS = {
    "admin": "1234",      # Contraseña Gerencia
    "cocina": "0000"      # Contraseña Operación
}

def registrar_acceso(sheet, usuario, rol):
    """Registra quién entra al sistema en la hoja LOG_ACCESOS."""
    try:
        try: ws = sheet.worksheet("LOG_ACCESOS")
        except:
            ws = sheet.add_worksheet(title="LOG_ACCESOS", rows="1000", cols="5")
            ws.append_row(["Fecha", "Hora", "Usuario", "Rol", "Status"])
        
        ahora = datetime.now(ZONA_HORARIA)
        ws.append_row([ahora.strftime("%Y-%m-%d"), ahora.strftime("%H:%M:%S"), usuario, rol, "OK"])
    except: pass

def login_form(sheet):
    """Pantalla de bloqueo y seguridad."""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔱 Tridenti Gastrobar")
        st.markdown("### Control de Acceso")
        
        usuario = st.selectbox("Selecciona tu Perfil", ["Seleccionar...", "Gerencia (Admin)", "Operación (Cocina)"])
        password = st.text_input("Contraseña", type="password")
        
        if st.button("🔓 INICIAR SESIÓN", type="primary", use_container_width=True):
            user_key = "admin" if "Gerencia" in usuario else "cocina"
            
            if usuario != "Seleccionar..." and password == USUARIOS.get(user_key):
                st.session_state["usuario_valido"] = True
                st.session_state["rol_actual"] = usuario
                registrar_acceso(sheet, usuario, user_key)
                st.success("✅ Acceso Correcto")
                st.rerun()
            else:
                st.error("❌ Contraseña incorrecta")

def main():
    # 1. CONEXIÓN A BASE DE DATOS
    sheet = conectar_google_sheets()
    if not sheet:
        st.error("🚨 Error crítico: No hay conexión con Google Sheets.")
        return

    # 2. VALIDACIÓN DE SESIÓN
    if "usuario_valido" not in st.session_state:
        st.session_state["usuario_valido"] = False

    if not st.session_state["usuario_valido"]:
        login_form(sheet)
        return

    # --- SISTEMA PRINCIPAL (SI YA ENTRÓ) ---
    
    rol = st.session_state["rol_actual"]
    nombre_app = "TRIDENTI V7"
    tema_app = "Auto"
    
    # Cargar Configuración Visual (Nombre del negocio, Tema)
    try:
        hoja_conf = sheet.worksheet("DB_CONFIG")
        df_conf = leer_datos_seguro(hoja_conf)
        if not df_conf.empty:
            config = dict(zip(df_conf['Parametro'], df_conf['Valor']))
            if "EMPRESA_NOMBRE" in config: nombre_app = config["EMPRESA_NOMBRE"]
            tema_app = config.get("MODO_OSCURO", "Auto")
    except: pass

    # Aplicar Tema CSS
    if "Dark" in tema_app:
        st.markdown("""<style>.stApp { background-color: #0E1117; color: white; }</style>""", unsafe_allow_html=True)
    elif "Light" in tema_app:
        st.markdown("""<style>.stApp { background-color: #FFFFFF; color: black; }</style>""", unsafe_allow_html=True)

    # --- MENÚ LATERAL ---
    with st.sidebar:
        st.title(nombre_app)
        st.caption(f"👤 {rol}")
        
        # MENÚ PARA GERENCIA (ADMIN)
        if rol == "Gerencia (Admin)":
            menu_options = [
                "Inteligencia",  # Dashboard General
                "Matriz BCG",    # Estrategia
                "Tesoreria",     # Dinero Real
                "Ventas",        # Histórico
                "Inventario",    # Kardex
                "Sugeridos",     # Compras Inteligentes
                "Compras",       # Registro Facturas
                "Gastos",        # Caja Menor
                "Insumos",       # Maestro
                "Recetas",       # Ingeniería
                "Proveedores",   # CRM
                "Auditoría",     # Control Físico
                "Reportar Daño", # Mermas
                "Configuración"  # Ajustes
            ]
            menu_icons = [
                "lightbulb",     # Inteligencia
                "stars",         # Matriz BCG
                "safe",          # Tesoreria
                "graph-up-arrow",# Ventas
                "clipboard-data",# Inventario
                "cart-check",    # Sugeridos
                "cart4",         # Compras
                "wallet2",       # Gastos
                "box-seam",      # Insumos
                "journal-text",  # Recetas
                "people",        # Proveedores
                "check-circle",  # Auditoría
                "exclamation-triangle", # Daños
                "gear"           # Config
            ]
            
        # MENÚ PARA OPERACIÓN (COCINA)
        else:
            menu_options = ["Reportar Daño", "Auditoría"]
            menu_icons = ["exclamation-triangle", "check-circle"]

        selected = option_menu(
            menu_title=None,
            options=menu_options,
            icons=menu_icons,
            default_index=0,
        )
        
        st.markdown("---")
        if st.button("🔒 CERRAR SESIÓN"):
            st.session_state["usuario_valido"] = False
            st.rerun()
            
        if rol == "Gerencia (Admin)":
            if st.button("🧹 LIMPIAR CACHÉ", type="secondary", help="Usa esto si ves datos viejos."):
                st.cache_data.clear()
                st.rerun()

    # --- ENRUTADOR DE MÓDULOS ---
    
    # 1. Estrategia & Finanzas
    if selected == "Inteligencia": inteligencia.show(sheet)
    elif selected == "Matriz BCG": matriz_bcg.show(sheet) # <--- NUEVO
    elif selected == "Tesoreria": tesoreria.show(sheet)
    elif selected == "Ventas": ventas.show(sheet)
    
    # 2. Operación & Inventario
    elif selected == "Inventario": inventario.show(sheet)
    elif selected == "Sugeridos": sugerido.show(sheet)
    elif selected == "Compras": compras.show(sheet)
    elif selected == "Gastos": gastos.show(sheet)
    
    # 3. Ingeniería & Maestros
    elif selected == "Insumos": insumos.show(sheet)
    elif selected == "Recetas": recetas.show(sheet)
    elif selected == "Proveedores": proveedores.show(sheet)
    
    # 4. Control & Ajustes
    elif selected == "Auditoría": auditoria_inv.show(sheet)
    elif selected == "Reportar Daño": bajas.show(sheet)
    elif selected == "Configuración": configuracion.show(sheet)

if __name__ == "__main__":
    main()