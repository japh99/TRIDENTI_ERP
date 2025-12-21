import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
import base64
import uuid
import pandas as pd
from datetime import datetime
import pytz
import cloudinary
import cloudinary.uploader
import time

# --- CONFIGURACIÓN ---
ZONA_HORARIA = pytz.timezone('America/Bogota')

# --- CONFIGURACIÓN DE CLOUDINARY (SISTEMA SEGURO) ---
# Este bloque busca las llaves que configuraste en el panel de Render
try:
    cloudinary.config( 
        cloud_name = os.environ.get("CLOUDINARY_NAME"), 
        api_key = os.environ.get("CLOUDINARY_API_KEY"), 
        api_secret = os.environ.get("CLOUDINARY_API_SECRET"), 
        secure = True
    )
except Exception as e:
    st.error(f"Error crítico en Cloudinary: {e}")

# --- FUNCIONES DE UTILIDAD ---

def limpiar_numero(valor):
    """Limpia strings de moneda y convierte a float."""
    if pd.isna(valor) or valor is None or valor == "": 
        return 0.0
    try:
        if isinstance(valor, (int, float)):
            return float(valor)
        limpio = str(valor).replace('$', '').replace(' ', '').replace(',', '').strip()
        return float(limpio) if limpio else 0.0
    except:
        return 0.0

def generar_id():
    """Genera ID único corto."""
    return str(uuid.uuid4().hex)[:5].upper()

def leer_datos_seguro(hoja):
    """Lee datos de Google Sheets evitando errores de cuota."""
    for i in range(3):
        try:
            data = hoja.get_all_values()
            if len(data) < 2:
                if len(data) == 1:
                    return pd.DataFrame(columns=[str(h).strip() for h in data[0]])
                return pd.DataFrame()
            headers = [str(h).strip() for h in data[0]]
            return pd.DataFrame(data[1:], columns=headers)
        except Exception as e:
            if "429" in str(e):
                time.sleep(2)
                continue
            return pd.DataFrame()
    return pd.DataFrame()

def limpiar_cache():
    st.cache_data.clear()

@st.cache_resource(ttl=600)
def conectar_google_sheets():
    """Conecta con la base de datos en Google Sheets."""
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = None
    
    try:
        # 1. Intento por variable Base64 (Render)
        b64_key = os.environ.get("GCP_B64")
        if b64_key:
            try:
                json_str = base64.b64decode(b64_key.strip().strip('"').strip("'")).decode("utf-8")
                creds_dict = json.loads(json_str)
            except: pass

        # 2. Intento por JSON directo (Render/Secrets)
        if not creds_dict:
            json_raw = os.environ.get("GCP_SERVICE_ACCOUNT")
            if json_raw:
                try: creds_dict = json.loads(json_raw)
                except: pass

        # 3. Intento por Secrets de Streamlit
        if not creds_dict:
            try:
                if hasattr(st, "secrets") and "GCP" in st.secrets:
                    creds_dict = json.loads(st.secrets["GCP"]["GCP_SERVICE_ACCOUNT"])
            except: pass

        if not creds_dict:
            st.error("No se encontraron credenciales de Google Sheets.")
            return None

        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # CAMBIAR POR EL NOMBRE EXACTO DE TU EXCEL SI ES DIFERENTE
        return client.open("TRIDENTI_DB_V7")
    
    except Exception as e:
        st.error(f"Error de conexión Sheets: {e}")
        return None

def subir_foto_drive(archivo, subcarpeta=None, carpeta_raiz="TRIDENTI_SOPORTES"):
    """Sube archivos a Cloudinary organizados por carpetas."""
    try:
        ahora = datetime.now(ZONA_HORARIA)
        ruta = f"{carpeta_raiz}/{ahora.year}/{ahora.strftime('%m-%b')}/{ahora.day:02d}"
        
        if subcarpeta:
            sub_limpio = str(subcarpeta).strip().upper().replace(" ", "_")
            ruta += f"/{sub_limpio}"
        
        res = cloudinary.uploader.upload(
            archivo, 
            folder=ruta, 
            resource_type="auto"
        )
        return res.get("secure_url")
    
    except Exception as e:
        print(f"Error Cloudinary: {e}")
        return f"Error en subida: {e}"
