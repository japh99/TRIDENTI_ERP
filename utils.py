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
ID_CARPETA_DRIVE = "1OYsctJyo75JlZm9MLiAfTuHKtvq1bpF6"
ZONA_HORARIA = pytz.timezone('America/Bogota')

# Configurar Cloudinary con bloque de seguridad
try:
    cloudinary.config( 
      cloud_name = "deilmyfio", 
      api_key = "487111251418656", 
      api_secret = "FYldB0cZfK2XC_6DpQGIn1MIyhE", 
      secure = True
    )
except: pass

def limpiar_numero(valor):
    if not valor: return 0.0
    try: return float(str(valor).replace('$', '').replace(',', '').strip())
    except: return 0.0

def generar_id():
    return str(uuid.uuid4().hex)[:5].upper()

def leer_datos_seguro(hoja):
    for i in range(3):
        try:
            data = hoja.get_all_values()
            if len(data) < 2: return pd.DataFrame()
            headers = [str(h).strip() for h in data[0]]
            return pd.DataFrame(data[1:], columns=headers)
        except Exception as e:
            if "429" in str(e): time.sleep(2); continue
            return pd.DataFrame()
    return pd.DataFrame()

def limpiar_cache():
    st.cache_data.clear()

@st.cache_resource(ttl=600)
def conectar_google_sheets():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = None
    
    try:
        # ---------------------------------------------------------
        # ESTRATEGIA 1: Variable Base64 (Ideal para Render)
        # ---------------------------------------------------------
        b64_key = os.environ.get("GCP_B64")
        if b64_key:
            try:
                # Limpiar comillas si se colaron
                b64_key = b64_key.strip().strip('"').strip("'")
                json_str = base64.b64decode(b64_key).decode("utf-8")
                creds_dict = json.loads(json_str)
            except Exception as e:
                print(f"Error decodificando B64: {e}")

        # ---------------------------------------------------------
        # ESTRATEGIA 2: Variable JSON Directa (Plan B)
        # ---------------------------------------------------------
        if not creds_dict:
            json_raw = os.environ.get("GCP_SERVICE_ACCOUNT")
            if json_raw:
                try: creds_dict = json.loads(json_raw)
                except: pass

        # ---------------------------------------------------------
        # ESTRATEGIA 3: Secrets Locales (Solo si existe el archivo)
        # ---------------------------------------------------------
        if not creds_dict:
            try:
                # Verificamos si existe el atributo secrets antes de llamarlo
                if hasattr(st, "secrets") and "GCP" in st.secrets:
                    creds_dict = json.loads(st.secrets["GCP"]["GCP_SERVICE_ACCOUNT"])
            except: pass

        # ---------------------------------------------------------
        # CONEXIÓN FINAL
        # ---------------------------------------------------------
        if not creds_dict:
            # Si llegamos aquí, no hay llaves. No rompemos la app, solo avisamos.
            st.error("⚠️ Error: No se encontraron credenciales de Google.")
            return None

        # Arreglo de saltos de línea para llaves privadas
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open("TRIDENTI_DB_V7")

    except Exception as e:
        st.error(f"❌ Error Conexión: {e}")
        return None

def subir_foto_drive(archivo, subcarpeta=None, carpeta_raiz="TRIDENTI_FACTURAS"):
    try:
        hoy = datetime.now(ZONA_HORARIA)
        ruta = f"{carpeta_raiz}/{hoy.year}/{hoy.strftime('%m-%b')}/{hoy.day:02d}"
        if subcarpeta: ruta += f"/{subcarpeta}"
        res = cloudinary.uploader.upload(archivo, folder=ruta, resource_type="auto")
        return res.get("secure_url")
    except Exception as e: return f"Error Cloudinary: {e}"
