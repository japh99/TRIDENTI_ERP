import streamlit as st
import pandas as pd
from datetime import datetime
import calendar
import time
from utils import conectar_google_sheets, subir_foto_drive, generar_id, leer_datos_seguro, limpiar_numero, ZONA_HORARIA

# --- CONFIGURACIÓN ---
HOJA_CONFIG = "DB_CONFIG"
HOJA_PAGOS = "LOG_PAGOS_GASTOS"

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

def cargar_config_gastos(sheet):
    """Lee los gastos fijos evitando duplicados en la carga."""
    try:
        ws = sheet.worksheet(HOJA_CONFIG)
        # Usamos leer_datos_seguro pero nos aseguramos de no cachear aquí
        data = ws.get_all_records()
        df_config = pd.DataFrame(data)
        
        gastos = []
        sugeridos = ["Arriendo Local", "Nómina Fija", "Servicios Públicos", "Internet", "Marketing", "Contador", "Mantenimiento"]
        encontrados = set()

        if not df_config.empty:
            # Filtrar solo parámetros que empiecen por GASTO_FIJO_
            mask = df_config['Parametro'].str.startswith("GASTO_FIJO_", na=False)
            df_gastos = df_config[mask]
            
            for _, row in df_gastos.iterrows():
                param = str(row['Parametro'])
                # Convertir ID técnico a nombre legible (GASTO_FIJO_Nomina_Fija -> Nómina Fija)
                nombre = param.replace("GASTO_FIJO_", "").replace("_", " ")
                
                valor_raw = str(row.get("Valor", "0|5|Mensual"))
                parts = valor_raw.split("|")
                
                gastos.append({
                    "Concepto": nombre,
                    "Valor Total Mensual": limpiar_numero(parts[0]),
                    "Día de Pago": int(limpiar_numero(parts[1] if len(parts) > 1 else 5)),
                    "Frecuencia": parts[2] if len(parts) > 2 else "Mensual"
                })
                encontrados.add(nombre)
        
        # Completar con sugeridos si no existen
        for s in sugeridos:
            if s not in encontrados:
                gastos.append({"Concepto": s, "Valor Total Mensual": 0.0, "Día de Pago": 5, "Frecuencia": "Mensual"})
                
        return pd.DataFrame(gastos)
    except:
        return pd.DataFrame(columns=["Concepto", "Valor Total Mensual", "Día de Pago", "Frecuencia"])

def guardar_config_gastos(sheet, df_editado):
    """Sobrescribe la configuración limpiando el caché para evitar duplicados."""
    try:
        ws = sheet.worksheet(HOJA_CONFIG)
        # 1. Obtener TODO lo que hay en el Excel actualmente
        data_actual = ws.get_all_records()
        df_actual = pd.DataFrame(data_actual)
        
        # 2. Mantener lo que NO es gasto fijo
        if not df_actual.empty:
            df_final = df_actual[~df_actual['Parametro'].str.startswith("GASTO_FIJO_", na=False)].copy()
        else:
            df_final = pd.DataFrame(columns=["Parametro", "Valor", "Descripcion"])

        # 3. Preparar los nuevos gastos editados
        nuevos_filas = []
        for _, row in df_editado.iterrows():
            conc = str(row["Concepto"]).strip().replace(" ", "_")
            if conc:
                nuevos_filas.append({
                    "Parametro": f"GASTO_FIJO_{conc}",
                    "Valor": f"{row['Valor Total Mensual']}|{int(row['Día de Pago'])}|{row['Frecuencia']}",
                    "Descripcion": f"Carga fabril: {row['Concepto']}"
                })
        
        df_nuevos = pd.DataFrame(nuevos_filas)
        
        # 4. Unir y limpiar
        df_update = pd.concat([df_final, df_nuevos], ignore_index=True)
        df_update = df_update[["Parametro", "Valor", "Descripcion"]]

        # 5. ACTUALIZACIÓN CRÍTICA: BORRAR Y ESCRIBIR
        ws.clear()
        ws.update([df_update.columns.values.tolist()] + df_update.values.tolist())
        
        # 6. LIMPIAR CACHÉ DE STREAMLIT (Esto evita que sigas viendo lo viejo)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False

# --- El resto del código de registrar_pago_realizado y show se mantiene igual ---
# Solo asegúrate de llamar a guardar_config_gastos en el botón.
