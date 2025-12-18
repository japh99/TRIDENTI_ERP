import requests
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
import pytz

# --- CONFIGURACIÓN ---
NOMBRE_HOJA_MENU = "DB_MENU_LOYVERSE"

def conectar_google_sheets_script():
    try:
        # Busca el secreto en el entorno (cuando corre en la nube)
        json_creds = os.environ.get('GCP_SERVICE_ACCOUNT')
        
        # Si no lo encuentra (estás en local), intenta buscar el archivo físico
        if not json_creds:
            if os.path.exists("credenciales.json"): # Nombre de tu archivo local si lo tienes
                with open("credenciales.json") as f:
                    creds_dict = json.load(f)
            else:
                # Fallback: Intenta leer de streamlit secrets si se ejecuta desde la app
                try:
                    import streamlit as st
                    json_creds = st.secrets["GCP_SERVICE_ACCOUNT"]
                    creds_dict = json.loads(json_creds)
                except:
                    print("❌ No se encontraron credenciales.")
                    return None
        else:
            creds_dict = json.loads(json_creds)

        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open("TRIDENTI_DB_V7")
    except Exception as e:
        print(f"❌ Error conexión DB: {e}")
        return None

def obtener_token():
    # Intenta obtener el token de entorno o streamlit secrets
    token = os.environ.get('LOYVERSE_TOKEN')
    if not token:
        try:
            import streamlit as st
            token = st.secrets["LOYVERSE_TOKEN"]
        except:
            # Token de respaldo directo (Solo si fallan los secrets)
            token = "2af9f2845c0b4417925d357b63cfab86"
    return token

def descargar_menu():
    print("⏳ Iniciando descarga de menú Loyverse...")
    
    token = obtener_token()
    url = "https://api.loyverse.com/v1.0/items"
    headers = {"Authorization": f"Bearer {token}"}
    
    productos = []
    cursor = None
    
    while True:
        params = {"limit": 250}
        if cursor: params["cursor"] = cursor
        
        try:
            r = requests.get(url, headers=headers, params=params)
            data = r.json()
            items = data.get("items", [])
            
            for i in items:
                nombre = i.get("item_name", "Sin Nombre")
                id_item = i.get("id", "")
                
                # Obtener variantes (Precios y Tamaños)
                variants = i.get("variants", [])
                for v in variants:
                    nombre_final = nombre
                    if len(variants) > 1 and v.get("option1_value"):
                         nombre_final = f"{nombre} - {v.get('option1_value')}"
                    
                    precio = v.get("default_price", 0)
                    costo = v.get("cost", 0)
                    id_var = v.get("variant_id", "")
                    sku = v.get("sku", "")
                    
                    productos.append([id_var, nombre_final, precio, costo, sku, id_item])
            
            cursor = data.get("cursor")
            if not cursor: break
            
        except Exception as e:
            print(f"❌ Error API: {e}")
            break
            
    print(f"✅ Se encontraron {len(productos)} productos.")
    return productos

def guardar_en_sheets(productos):
    sheet = conectar_google_sheets_script()
    if not sheet: return
    
    try:
        try: ws = sheet.worksheet(NOMBRE_HOJA_MENU)
        except: ws = sheet.add_worksheet(title=NOMBRE_HOJA_MENU, rows="2000", cols="10")
        
        ws.clear()
        ws.append_row(["ID_Variante", "Nombre_Producto", "Precio", "Costo", "SKU", "ID_Producto_Padre"])
        ws.append_rows(productos)
        print("💾 Guardado exitoso en Google Sheets.")
        
    except Exception as e:
        print(f"❌ Error guardando: {e}")

if __name__ == "__main__":
    prods = descargar_menu()
    if prods:
        guardar_en_sheets(prods)