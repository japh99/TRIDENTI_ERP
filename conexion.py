import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json

print("🚀 INICIANDO PROTOCOLO DE CONEXIÓN...")

try:
    # 1. BUSCAR LA LLAVE EN LA CAJA FUERTE DE GITHUB
    json_creds = os.environ.get('GCP_SERVICE_ACCOUNT')

    if not json_creds:
        print("❌ ERROR CRÍTICO: No encontré el secreto 'GCP_SERVICE_ACCOUNT'.")
        print("Asegúrate de haberlo guardado en GitHub Settings > Secrets > Codespaces.")
        exit()

    # 2. AUTENTICAR AL ROBOT
    creds_dict = json.loads(json_creds)
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    print("📡 Robot autenticado. Buscando el archivo Excel...")

    # 3. ABRIR TU HOJA DE CÁLCULO
    # OJO: Debe llamarse EXACTAMENTE igual a tu archivo en Drive
    sheet = client.open("TRIDENTI_DB_V7")
    
    # 4. ESCRIBIR UNA PRUEBA EN LA PESTAÑA 'DB_INSUMOS'
    hoja = sheet.worksheet("DB_INSUMOS")
    
    print("✍️ Escribiendo en la hoja...")
    hoja.update_acell('A2', 'TEST-ROBOT')
    hoja.update_acell('B2', '¡HOLA GERENTE! LA CONEXIÓN ES EXITOSA 🐍')
    hoja.update_acell('C2', 'UNIDAD')

    print("✅ ¡PRUEBA SUPERADA! Ve a tu iPad y revisa el Excel.")

except Exception as e:
    print(f"❌ FALLO DE CONEXIÓN: {e}")
    print("Consejo: Verifica que hayas compartido el Excel con el correo del robot (client_email).")