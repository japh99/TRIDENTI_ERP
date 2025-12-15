import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import os
import json
import uuid
import pandas as pd
from datetime import datetime
import pytz
import cloudinary
import cloudinary.uploader

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

# --- LECTURA SEGURA (SIN CACHÉ PARA EVITAR CONFUSIÓN) ---
# Hemos quitado el @st.cache_data aquí para obligar a leer la hoja correcta siempre
def leer_datos_seguro(hoja):
    try:
        data = hoja.get_all_values()
        if len(data) < 2: return pd.DataFrame()
        
        # Limpieza de encabezados
        headers = [str(h).strip() for h in data[0]]
        
        rows = data[1:]
        df = pd.DataFrame(rows, columns=headers)
        
        # Eliminar columnas vacías
        df = df.loc[:, df.columns != '']
        
        return df
    except Exception as e:
        return pd.DataFrame()

# Función auxiliar por si algún módulo la llama
def limpiar_cache():
    st.cache_data.clear()

# --- CONEXIÓN (ESTA SÍ LLEVA CACHÉ PORQUE ES PESADA) ---
@st.cache_resource
def conectar_google_sheets():
    try:
        json_creds = os.environ.get('GCP_SERVICE_ACCOUNT')
        if not json_creds: return None
        creds_dict = json.loads(json_creds)
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open("TRIDENTI_DB_V7")
        return sheet
    except Exception as e:
        st.error(f"Error Conexión Sheets: {e}")
        return None

# --- SUBIDA FOTOS ---
def subir_foto_drive(archivo):
    try:
        hoy_co = datetime.now(ZONA_HORARIA)
        meses = {1:"01-Ene", 2:"02-Feb", 3:"03-Mar", 4:"04-Abr", 5:"05-May", 6:"06-Jun", 7:"07-Jul", 8:"08-Ago", 9:"09-Sep", 10:"10-Oct", 11:"11-Nov", 12:"12-Dic"}
        ruta = f"TRIDENTI_FACTURAS/{hoy_co.year}/{meses[hoy_co.month]}/{hoy_co.day:02d}"
        nombre = f"FAC_{hoy_co.strftime('%H%M%S')}_{archivo.name.split('.')[0]}"
        
        res = cloudinary.uploader.upload(archivo, folder=ruta, public_id=nombre, resource_type="auto")
        return res.get("secure_url")
    except Exception as e:
        return f"Error Cloudinary: {e}"