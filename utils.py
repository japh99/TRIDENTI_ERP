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
# Zona horaria local
ZONA_HORARIA = pytz.timezone('America/Bogota')

# Configurar Cloudinary (Basado en tus credenciales)
try:
    cloudinary.config( 
        cloud_name = "deilmyfio", 
        api_key = "487111251418656", 
        api_secret = "FYldB0cZfK2XC_6DpQGIn1MIyhE", 
        secure = True
    )
except Exception as e:
    print(f"Error configurando Cloudinary: {e}")

# --- FUNCIONES DE UTILIDAD ---

def limpiar_numero(valor):
    """Convierte cualquier entrada (moneda, texto, etc) a un float limpio."""
    if pd.isna(valor) or valor is None or valor == "": 
        return 0.0
    try:
        if isinstance(valor, (int, float)):
            return float(valor)
        # Quitar símbolos de moneda, espacios y comas de miles
        limpio = str(valor).replace('$', '').replace(' ', '').replace(',', '').strip()
        # Si después de limpiar queda vacío
        if not limpio: return 0.0
        return float(limpio)
    except:
        return 0.0

def generar_id():
    """Genera un ID corto único de 5 caracteres en mayúsculas."""
    return str(uuid.uuid4().hex)[:5].upper()

def leer_datos_seguro(hoja):
    """Lee datos de una hoja manejando el error 429 (Cuota de Google) y hojas vacías."""
    for i in range(3): # Reintentar hasta 3 veces
        try:
            data = hoja.get_all_values()
            if len(data) < 2: # Solo hay encabezados o está vacía
                if len(data) == 1:
                    return pd.DataFrame(columns=[str(h).strip() for h in data[0]])
                return pd.DataFrame()
            
            headers = [str(h).strip() for h in data[0]]
            return pd.DataFrame(data[1:], columns=headers)
        except Exception as e:
            if "429" in str(e):
                time.sleep(2) # Esperar si Google nos bloquea temporalmente
                continue
            return pd.DataFrame()
    return pd.DataFrame()

def limpiar_cache():
    """Limpia el caché de Streamlit."""
    st.cache_data.clear()

@st.cache_resource(ttl=600)
def conectar_google_sheets():
    """Establece conexión con Google Sheets usando Service Account."""
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = None
    
    try:
        # ESTRATEGIA 1: Variable Base64 (Para Render/Despliegue)
        b64_key = os.environ.get("GCP_B64")
        if b64_key:
            try:
                b64_key = b64_key.strip().strip('"').strip("'")
                json_str = base64.b64decode(b64_key).decode("utf-8")
                creds_dict = json.loads(json_str)
            except Exception as e:
                print(f"Error decodificando B64: {e}")

        # ESTRATEGIA 2: Variable JSON Directa
        if not creds_dict:
            json_raw = os.environ.get("GCP_SERVICE_ACCOUNT")
            if json_raw:
                try: creds_dict = json.loads(json_raw)
                except: pass

        # ESTRATEGIA 3: Secrets de Streamlit
        if not creds_dict:
            try:
                if hasattr(st, "secrets") and "GCP" in st.secrets:
                    creds_dict = json.loads(st.secrets["GCP"]["GCP_SERVICE_ACCOUNT"])
            except: pass

        if not creds_dict:
            st.error("❌ Error: No se encontraron credenciales de Google.")
            return None

        # Arreglo de saltos de línea en la llave privada
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # Nombre de tu archivo principal
        return client.open("TRIDENTI_DB_V7")
    
    except Exception as e:
        st.error(f"❌ Error de Conexión: {e}")
        return None

def subir_foto_drive(archivo, subcarpeta=None, carpeta_raiz="TRIDENTI_SOPORTES"):
    """
    Sube un archivo a Cloudinary organizándolo por carpetas.
    Nota: Se mantiene el nombre 'drive' por compatibilidad con tu código, 
    pero la carga es en Cloudinary.
    """
    try:
        ahora = datetime.now(ZONA_HORARIA)
        
        # Crear ruta organizada: RAIZ/AÑO/MES/DIA/SUBCARPETA
        ruta = f"{carpeta_raiz}/{ahora.year}/{ahora.strftime('%m-%b')}/{ahora.day:02d}"
        if subcarpeta:
            # Limpiar nombre de subcarpeta para URL
            sub_limpio = str(subcarpeta).strip().upper().replace(" ", "_")
            ruta += f"/{sub_limpio}"
        
        # Subida a Cloudinary
        res = cloudinary.uploader.upload(
            archivo, 
            folder=ruta, 
            resource_type="auto"
        )
        
        return res.get("secure_url") # Retorna el link HTTPS directo
    
    except Exception as e:
        print(f"Error Cloudinary: {e}")
        return f"Error Cloudinary: {e}"
