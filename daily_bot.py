import pandas as pd
import requests
import pytz
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta, time as dt_time

# --- CONFIGURACIÓN ---
ZONA_HORARIA = pytz.timezone('America/Bogota')
NOMBRE_HOJA = "LOG_VENTAS_LOYVERSE"

# ⚠️ CAMBIA ESTO A LA FECHA QUE FALTA PARA FORZAR LA DESCARGA
# Formato: YYYY-MM-DD. Si lo dejas None, busca la de ayer automáticamente.
FECHA_MANUAL = "2025-12-16" 

def conectar_google_sheets_bot():
    print("🔌 Intentando conectar con Google Sheets...")
    try:
        json_creds = os.environ.get('GCP_SERVICE_ACCOUNT')
        if not json_creds:
            print("❌ ERROR CRÍTICO: No existe el secreto GCP_SERVICE_ACCOUNT")
            return None
            
        creds_dict = json.loads(json_creds)
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        print("✅ Conexión con Google exitosa.")
        return client.open("TRIDENTI_DB_V7")
    except Exception as e:
        print(f"❌ ERROR CONEXIÓN DB: {e}")
        return None

def ejecutar_cierre_ayer():
    print("🤖 --- INICIANDO ROBOT DIAGNÓSTICO ---")
    
    # 1. DEFINIR FECHA
    if FECHA_MANUAL:
        print(f"🔧 MODO MANUAL ACTIVADO: Buscando fecha {FECHA_MANUAL}")
        ayer = datetime.strptime(FECHA_MANUAL, "%Y-%m-%d").date()
    else:
        ahora_co = datetime.now(ZONA_HORARIA)
        ayer = (ahora_co - timedelta(days=1)).date()
        print(f"📅 Modo Automático: Buscando ventas de AYER ({ayer})")

    token = os.environ.get('LOYVERSE_TOKEN')
    if not token:
        print("❌ ERROR: Falta Token Loyverse")
        return

    # 2. DEFINIR RANGO DE TIEMPO
    inicio_dia = datetime.combine(ayer, dt_time.min).replace(tzinfo=ZONA_HORARIA)
    fin_dia = datetime.combine(ayer, dt_time.max).replace(tzinfo=ZONA_HORARIA)

    print(f"⏳ Rango de búsqueda (Colombia): {inicio_dia} hasta {fin_dia}")
    
    # Convertir a UTC para Loyverse
    iso_inicio = inicio_dia.astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    iso_fin = fin_dia.astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    print(f"🌍 Rango de búsqueda (UTC Loyverse): {iso_inicio} hasta {iso_fin}")

    # 3. CONEXIÓN EXCEL
    sheet = conectar_google_sheets_bot()
    if not sheet: return

    try:
        ws = sheet.worksheet(NOMBRE_HOJA)
        # OMITIMOS EL BLOQUEO DE DUPLICADOS PARA ESTA PRUEBA
        print("⚠️ AVISO: El bloqueo de duplicados está DESACTIVADO para esta prueba.")
    except:
        print("ℹ️ La hoja no existe. Se creará.")
        ws = sheet.add_worksheet(title=NOMBRE_HOJA, rows="1000", cols="20")

    # 4. DESCARGAR
    params = {
        "created_at_min": iso_inicio,
        "created_at_max": iso_fin,
        "limit": 250
    }
    headers = {"Authorization": f"Bearer {token}"}
    
    ventas_detalle = []
    cursor = None
    
    while True:
        if cursor: params["cursor"] = cursor
        
        print("📡 Enviando petición a Loyverse...")
        r = requests.get("https://api.loyverse.com/v1.0/receipts", headers=headers, params=params)
        
        if r.status_code != 200:
            print(f"❌ ERROR API LOYVERSE ({r.status_code}): {r.text}")
            break
            
        data = r.json()
        receipts = data.get("receipts", [])
        print(f"📦 Loyverse respondió: {len(receipts)} recibos en este lote.")
        
        if len(receipts) == 0:
            print("👀 Loyverse dice que no hay más recibos.")
            break

        for r_item in receipts:
            # Validar fecha
            fecha_col = datetime.fromisoformat(r_item["created_at"].replace("Z", "+00:00")).astimezone(ZONA_HORARIA)
            
            # Filtro estricto de día
            if fecha_col.date() != ayer:
                continue 

            hora = fecha_col.strftime("%H:%M")
            recibo_no = r_item.get("receipt_number", "S/N")
            pagos = r_item.get("payments", [])
            metodo = pagos[0].get("name", "Efectivo") if pagos else "Efectivo"
            
            items = r_item.get("line_items", [])
            
            if not items:
                # Venta manual
                row = [fecha_col.strftime("%Y-%m-%d"), hora, str(recibo_no), "MANUAL", "Venta Manual", 1, r_item.get("total_money", 0), metodo, metodo]
                ventas_detalle.append(row)
            else:
                for item in items:
                    nombre_plato = item.get("item_name", "Desconocido")
                    if item.get("variant_name"): nombre_plato += f" {item.get('variant_name')}"
                    
                    row = [
                        fecha_col.strftime("%Y-%m-%d"), 
                        hora, 
                        str(recibo_no), 
                        str(item.get("item_id", "")), 
                        nombre_plato.strip(), 
                        item.get("quantity", 1), 
                        item.get("total_money", 0), 
                        metodo, 
                        metodo
                    ]
                    ventas_detalle.append(row)
        
        cursor = data.get("cursor")
        if not cursor: break

    # 5. RESULTADO
    print(f"📊 Total filas procesadas para guardar: {len(ventas_detalle)}")

    if ventas_detalle:
        try:
            print("💾 Intentando escribir en Google Sheets...")
            ws.append_rows(ventas_detalle)
            print("✅ ¡GUARDADO EXITOSO! Revisa tu Excel ahora.")
        except Exception as e:
            print(f"❌ Error escribiendo en Excel: {e}")
    else:
        print("🤷‍♂️ El robot funcionó, pero no encontró ventas válidas para esa fecha.")

if __name__ == "__main__":
    ejecutar_cierre_ayer()