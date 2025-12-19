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
    """Intenta leer hasta 5 veces si Google está ocupado (Error 429)"""
    max_intentos = 5
    for i in range(max_intentos):
        try:
            data = hoja.get_all_values()
            if len(data) < 2: return pd.DataFrame()
            headers = [str(h).strip() for h in data[0]]
            # Crear DF solo con columnas que tengan nombre
            df = pd.DataFrame(data[1:], columns=headers)
            df = df.loc[:, df.columns != '']
            return df
        except Exception as e:
            if "429" in str(e) or "Quota" in str(e):
                # Espera progresiva: 2s, 4s, 6s...
                time.sleep(2 * (i + 1))
                continue
            else:
                return pd.DataFrame()
    return pd.DataFrame()

def limpiar_cache():
    st.cache_data.clear()

@st.cache_resource(ttl=600)
def conectar_google_sheets():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = None
    
    try:
        # 1. Recuperar Credenciales (Soporta Streamlit Cloud y Local)
        if "GCP" in st.secrets:
            json_str = st.secrets["GCP"]["GCP_SERVICE_ACCOUNT"]
            creds_dict = json.loads(json_str)
        elif os.environ.get('GCP_SERVICE_ACCOUNT'):
             creds_dict = json.loads(os.environ.get('GCP_SERVICE_ACCOUNT'))

        if not creds_dict:
            st.error("❌ No se encontraron las credenciales [GCP] en Secrets.")
            return None

        # Corrección de llave privada
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

        # Autenticación
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # 2. INTENTO DE CONEXIÓN CON REINTENTOS (ANTI-ERROR 429)
        for i in range(5):
            try:
                sheet = client.open("TRIDENTI_DB_V7")
                return sheet
            except Exception as e:
                # Si es error de cuota, esperar y reintentar
                if "429" in str(e) or "Quota" in str(e):
                    time.sleep(2 + i)
                    continue
                else:
                    raise e # Si es otro error, lanzarlo
                    
        return None

    except Exception as e:
        # Solo mostrar el error si es crítico, para no asustar
        if "429" not in str(e):
            st.error(f"🔥 Error Técnico: {e}")
        return None

def subir_foto_drive(archivo, subcarpeta=None, carpeta_raiz="TRIDENTI_FACTURAS"):
    try:
        hoy_co = datetime.now(ZONA_HORARIA)
        meses = {1:"01-Ene", 2:"02-Feb", 3:"03-Mar", 4:"04-Abr", 5:"05-May", 6:"06-Jun", 7:"07-Jul", 8:"08-Ago", 9:"09-Sep", 10:"10-Oct", 11:"11-Nov", 12:"12-Dic"}
        ruta = f"{carpeta_raiz}/{hoy_co.year}/{meses[hoy_co.month]}/{hoy_co.day:02d}"
        if subcarpeta: ruta += f"/{subcarpeta}"
        res = cloudinary.uploader.upload(archivo, folder=ruta, resource_type="auto")
        return res.get("secure_url")
    except Exception as e: return f"Error Cloudinary: {e}"
