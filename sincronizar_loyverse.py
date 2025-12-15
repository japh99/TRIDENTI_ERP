import requests
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
import time

print("🍔 INICIANDO SINCRONIZACIÓN CON LOYVERSE (VERSIÓN BLINDADA)...")

# --- CONFIGURACIÓN ---
try:
    # 1. CONECTAR A GOOGLE SHEETS
    json_creds = os.environ.get('GCP_SERVICE_ACCOUNT')
    if not json_creds:
        print("❌ ERROR: No se encontró el secreto de Google (GCP_SERVICE_ACCOUNT).")
        exit()
        
    creds_dict = json.loads(json_creds)
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("TRIDENTI_DB_V7") 
    hoja_menu = sheet.worksheet("DB_MENU_LOYVERSE")

    # 2. OBTENER TOKEN DE LOYVERSE
    loyverse_token = os.environ.get('LOYVERSE_TOKEN')
    if not loyverse_token:
        print("❌ ERROR: No se encontró el secreto de Loyverse (LOYVERSE_TOKEN).")
        exit()

except Exception as e:
    print(f"❌ Error de Configuración Inicial: {e}")
    exit()

# --- FUNCIONES ---

def traer_todos_los_productos():
    print("📡 Contactando a Loyverse API...")
    url = "https://api.loyverse.com/v1.0/items"
    headers = {"Authorization": f"Bearer {loyverse_token}"}
    
    todos_los_items = []
    cursor = None 
    
    while True:
        try:
            params = {"limit": 50} 
            if cursor:
                params["cursor"] = cursor
                
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code != 200:
                print(f"❌ Error API Loyverse: {response.text}")
                break
                
            data = response.json()
            items = data.get('items', [])
            todos_los_items.extend(items)
            
            cursor = data.get('cursor')
            if not cursor:
                break 
        except Exception as e:
            print(f"⚠️ Error durante la descarga: {e}")
            break
            
    print(f"✅ Se descargaron {len(todos_los_items)} productos de Loyverse.")
    return todos_los_items

def procesar_datos(items):
    data_para_excel = []
    
    for item in items:
        # Usamos .get() para evitar errores si falta algún dato
        variants = item.get('variants', [])
        parent_name = item.get('item_name', 'Sin Nombre')
        cat_id = item.get('category_id', '')

        for variant in variants:
            variant_id = variant.get('variant_id', '')
            
            # Lógica segura para el nombre
            variant_name = variant.get('item_name') # Puede ser None
            full_name = parent_name
            
            # Solo agregamos el nombre de la variante si existe y es diferente al padre
            if variant_name and variant_name != parent_name:
                 full_name = f"{parent_name} - {variant_name}"
            
            price = variant.get('default_price', 0)
            sku = variant.get('sku', 'SIN-SKU')
            
            # Fila segura
            fila = [
                str(variant_id), 
                str(full_name), 
                str(cat_id), 
                str(sku), 
                price, 
                0, # Costo
                0, # Margen
                "PENDIENTE" # Semáforo
            ]
            data_para_excel.append(fila)
            
    return data_para_excel

# --- EJECUCIÓN ---

if __name__ == "__main__":
    try:
        items_raw = traer_todos_los_productos()

        if items_raw:
            datos_limpios = procesar_datos(items_raw)
            
            print(f"💾 Guardando {len(datos_limpios)} filas en Google Sheets...")
            
            # Limpiar hoja antigua (Preservando encabezados A1:H1)
            hoja_menu.batch_clear(["A2:H5000"]) 
            
            # Escribir nuevos datos
            if len(datos_limpios) > 0:
                hoja_menu.update(range_name="A2", values=datos_limpios)
                print("🎉 ¡ÉXITO TOTAL! Revisa tu Excel ahora.")
            else:
                print("⚠️ No se generaron datos para guardar.")

        else:
            print("⚠️ La lista de productos llegó vacía.")
            
    except Exception as e:
        print(f"❌ Ocurrió un error inesperado: {e}")