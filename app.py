import streamlit as st
from streamlit_option_menu import option_menu
from utils import conectar_google_sheets, leer_datos_seguro

# --- IMPORTACIÓN DE MÓDULOS ---
# Asegúrate de que existan los archivos en la carpeta modules/
from modules import insumos, recetas, compras, ventas, proveedores, configuracion, inteligencia

# --- CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Tridenti ERP V7", page_icon="🔱", layout="wide")

def main():
    # 1. CONEXIÓN
    sheet = conectar_google_sheets()
    
    # Intentar leer configuración personalizada (Nombre empresa, tema)
    nombre_app = "TRIDENTI V7"
    if sheet:
        try:
            hoja_conf = sheet.worksheet("DB_CONFIG")
            df_conf = leer_datos_seguro(hoja_conf)
            if not df_conf.empty:
                config = dict(zip(df_conf['Parametro'], df_conf['Valor']))
                if "EMPRESA_NOMBRE" in config: nombre_app = config["EMPRESA_NOMBRE"]
                
                # Tema Oscuro/Claro (Simulado)
                tema = config.get("MODO_OSCURO", "Auto")
                if "Dark" in tema:
                    st.markdown("""<style>.stApp { background-color: #0E1117; color: white; }</style>""", unsafe_allow_html=True)
                elif "Light" in tema:
                    st.markdown("""<style>.stApp { background-color: #FFFFFF; color: black; }</style>""", unsafe_allow_html=True)
        except: pass

    # 2. MENÚ LATERAL
    with st.sidebar:
        st.title(nombre_app)
        st.caption("Sistema de Gestión Gastronómica")
        
        # BOTÓN DE PÁNICO (Limpiar Caché)
        if st.button("🧹 REFRESCAR SISTEMA", type="primary"):
            st.cache_data.clear()
            st.rerun()
            
        selected = option_menu(
            menu_title=None,
            options=[
                "Insumos", 
                "Recetas", 
                "Compras", 
                "Proveedores", 
                "Inteligencia", # <--- NUEVO MÓDULO
                "Ventas", 
                "Configuración"
            ],
            icons=[
                "box-seam", 
                "journal-text", 
                "cart4", 
                "people", 
                "lightbulb", # Icono bombillo
                "graph-up-arrow", 
                "gear"
            ],
            default_index=0,
        )
    
    if not sheet: 
        st.error("🚨 Sin conexión a Google Sheets. Revisa 'utils.py' y tus credenciales.")
        return

    # 3. ENRUTADOR (ROUTER)
    # Aquí es donde estaba el error de identación. Ahora está corregido.
    
    if selected == "Insumos":
        insumos.show(sheet)
    
    elif selected == "Recetas":
        recetas.show(sheet)
        
    elif selected == "Compras":
        compras.show(sheet)
        
    elif selected == "Proveedores":
        proveedores.show(sheet)
        
    elif selected == "Inteligencia":
        inteligencia.show(sheet)  # <--- Esta línea ya tiene el espacio correcto
        
    elif selected == "Ventas":
        ventas.show(sheet)
        
    elif selected == "Configuración":
        configuracion.show(sheet)

if __name__ == "__main__":
    main()