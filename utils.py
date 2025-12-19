import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
import uuid
import pandas as pd
from datetime import datetime
import pytz
import cloudinary
import cloudinary.uploader
import time

# --- CONFIGURACIÓN ---
ID_CARPETA_DRIVE = "1OYsctJyo75JlZm9MLiAfTuHKtvq1bpF6"
ZONA_HORARIA = pytz.timezone('America/Bogota')

cloudinary.config( 
  cloud_name = "deilmyfio", 
  api_key = "487111251418656", 
  api_secret = "FYldB0cZfK2XC_6DpQGIn1MIyhE", 
  secure = True
)

def limpiar_numero(valor):
    if not valor: return 0.0
    try: return float(str(valor).replace('$', '').replace(',', '').strip())
    except: return 0.0

def generar_id():
    return str(uuid.uuid4().hex)[:5].upper()

def leer_datos_seguro(hoja):
    max_intentos = 3
    for i in range(max_intentos):
        try:
            data = hoja.get_all_values()
            if len(data) < 2: return pd.DataFrame()
            headers = [str(h).strip() for h in data[0]]
            return pd.DataFrame(data[1:], columns=headers)
        except Exception as e:
            if "429" in str(e): time.sleep(2 * (i+1)); continue
            return pd.DataFrame()
    return pd.DataFrame()

def limpiar_cache():
    st.cache_data.clear()

@st.cache_resource(ttl=600)
def conectar_google_sheets():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = None
    
    try:
        # INTENTO 1: Buscar en secrets.toml (Streamlit Cloud)
        if "GCP" in st.secrets:
            # Leer el string y convertirlo a JSON
            json_str = st.secrets["GCP"]["GCP_SERVICE_ACCOUNT"]
            creds_dict = json.loads(json_str)
        
        # INTENTO 2: Variable de entorno (Backup)
        elif os.environ.get('GCP_SERVICE_ACCOUNT'):
            creds_dict = json.loads(os.environ.get('GCP_SERVICE_ACCOUNT'))

        if not creds_dict:
            st.error("❌ No se encontraron las credenciales [GCP] en Secrets.")
            return None

        # CORRECCIÓN DE LA LLAVE PRIVADA
        # A veces el copy-paste rompe los saltos de línea (\n)
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

        # CONEXIÓN
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # INTENTO DE ABRIR LA HOJA
        # Esto confirmará si el robot tiene permiso
        sheet = client.open("TRIDENTI_DB_V7")
        return sheet

    except Exception as e:
        # ESTO ES LO QUE NECESITAMOS VER:
        st.error(f"🔥 ERROR TÉCNICO DETALLADO: {e}")
        return None

def subir_foto_drive(archivo, subcarpeta=None, carpeta_raiz="TRIDENTI_FACTURAS"):
    try:
        hoy = datetime.now(ZONA_HORARIA)
        ruta = f"{carpeta_raiz}/{hoy.year}/{hoy.strftime('%m-%b')}/{hoy.day:02d}"
        if subcarpeta: ruta += f"/{subcarpeta}"
        res = cloudinary.uploader.upload(archivo, folder=ruta, resource_type="auto")
        return res.get("secure_url")
    except Exception as e: return f"Error Cloudinary: {e}"
