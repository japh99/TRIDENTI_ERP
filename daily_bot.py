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

# 1. CONEXIÓN (Adaptada para GitHub Actions)
def conectar_google_sheets_bot():
    try:
        # En GitHub Actions, el secreto vendrá como variable de entorno
        json_creds = os.environ.get('GCP_SERVICE_ACCOUNT')
        if not json_creds:
            print("❌ No se encontró la credencial GCP_SERVICE_ACCOUNT")
            return None
            
        creds_dict = json.loads(json_creds)
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open("TRIDENTI_DB_V7")
    except Exception as e:
        print(f"❌ Error conexión DB: {e}")
        return None

# 2. DESCARGA (Lógica de Ventas reutilizada)
def ejecutar_cierre_ayer():
    print("🤖 INICIANDO ROBOT DE CIERRE AUTOMÁTICO...")
    
    # Calcular fecha de AYER (Si corre hoy a las 6 AM, cierra lo de ayer)
    hoy = datetime.now(ZONA_HORARIA)
    ayer = hoy.date() - timedelta(days=1)
    print(f"📅 Fecha objetivo: {ayer}")

    token = os.environ.get('LOYVERSE_TOKEN')
    if not token:
        print("❌ Falta Token Loyverse")
        return

    # Definir rango horario
    inicio_dia = datetime.combine(ayer, dt_time.min).replace(tzinfo=ZONA_HORARIA)
    fin_dia = datetime.combine(ayer, dt_time.max).replace(tzinfo=ZONA_HORARIA)

    params = {
        "created_at_min": inicio_dia.astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z'),
        "created_at_max": fin_dia.astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z'),
        "limit": 250
    }
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Conexión DB
    sheet = conectar_google_sheets_bot()
    if not sheet: return

    # Verificar duplicados
    try:
        ws = sheet.worksheet(NOMBRE_HOJA)
        fechas = ws.col_values(1)
        if str(ayer) in fechas:
            print(f"⚠️ El día {ayer} YA estaba registrado. No se duplica.")
            return
    except:
        pass # Si falla leyendo, asumimos que intenta escribir

    # Descargar API
    ventas = []
    cursor = None
    url = "https://api.loyverse.com/v1.0/receipts"

    while True:
        if cursor: params["cursor"] = cursor
        r = requests.get(url, headers=headers, params=params)
        if r.status_code != 200:
            print(f"❌ Error API: {r.text}")
            break
            
        data = r.json()
        receipts = data.get("receipts", [])
        
        for item in receipts:
            fecha_col = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00")).astimezone(ZONA_HORARIA)
            
            if fecha_col.date() == ayer:
                pagos = item.get("payments", [])
                metodo = pagos[0].get("name", "Efectivo") if pagos else "Efectivo"
                
                venta = [
                    fecha_col.strftime("%Y-%m-%d"),
                    fecha_col.strftime("%H:%M"),
                    item.get("receipt_number", "S/N"),
                    "TICKET", "Venta POS", 1,
                    item.get("total_money", 0),
                    metodo,
                    metodo 
                ]
                ventas.append(venta)
        
        cursor = data.get("cursor")
        if not cursor: break

    # Guardar
    if ventas:
        ws.append_rows(ventas)
        total = sum(v[6] for v in ventas)
        print(f"✅ ÉXITO: Se guardaron {len(ventas)} ventas. Total: ${total:,.0f}")
    else:
        print("ℹ️ No hubo ventas ayer.")

if __name__ == "__main__":
    ejecutar_cierre_ayer()