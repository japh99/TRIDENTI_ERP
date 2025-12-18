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

# --- CLOUDINARY ---
cloudinary.config( 
  cloud_name = "deilmyfio", 
  api_key = "487111251418656", 
  api_secret = "FYldB0cZfK2XC_6DpQGIn1MIyhE", 
  secure = True
)

# --- HERRAMIENTAS ---
def limpiar_numero(valor):
    if not valor: return 0.0
    if isinstance(valor, (int, float)): return float(valor)
    texto = str(valor).replace('$', '').replace(',', '').strip()
    try: return float(texto)
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
            rows = data[1:]
            df = pd.DataFrame(rows, columns=headers)
            df = df.loc[:, df.columns != '']
            return df
        except Exception as e:
            if "429" in str(e):
                time.sleep(2 * (i + 1))
                continue
            else:
                return pd.DataFrame()
    return pd.DataFrame()

def limpiar_cache():
    st.cache_data.clear()

@st.cache_resource(ttl=600)
def conectar_google_sheets():
    try:
        json_creds = os.environ.get('GCP_SERVICE_ACCOUNT')
        if not json_creds: return None
        creds_dict = json.loads(json_creds)
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open("TRIDENTI_DB_V7")
    except Exception as e:
        st.error(f"Error Conexión: {e}")
        return None

# --- SUBIDA FOTOS (MEJORADA PARA CARPETAS PRINCIPALES) ---
def subir_foto_drive(archivo, subcarpeta=None, carpeta_raiz="TRIDENTI_FACTURAS"):
    """
    Sube archivos a Cloudinary.
    - carpeta_raiz: La carpeta principal (Por defecto TRIDENTI_FACTURAS, pero puede ser COSTOS_FIJOS)
    - subcarpeta: La subcategoría (ej: NOMINA, INTERNET)
    """
    try:
        hoy_co = datetime.now(ZONA_HORARIA)
        meses = {1:"01-Ene", 2:"02-Feb", 3:"03-Mar", 4:"04-Abr", 5:"05-May", 6:"06-Jun", 7:"07-Jul", 8:"08-Ago", 9:"09-Sep", 10:"10-Oct", 11:"11-Nov", 12:"12-Dic"}
        
        # Ruta Estructurada: CARPETA_RAIZ / AÑO / MES / DIA / SUBCARPETA
        ruta = f"{carpeta_raiz}/{hoy_co.year}/{meses[hoy_co.month]}/{hoy_co.day:02d}"
        
        if subcarpeta:
            ruta += f"/{subcarpeta}"
            
        nombre = f"SOPORTE_{hoy_co.strftime('%H%M%S')}_{archivo.name.split('.')[0]}"
        
        res = cloudinary.uploader.upload(archivo, folder=ruta, public_id=nombre, resource_type="auto")
        return res.get("secure_url")
    except Exception as e:
        return f"Error Cloudinary: {e}"