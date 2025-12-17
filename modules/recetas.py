import streamlit as st
import pandas as pd
import requests
import json
import time
from utils import conectar_google_sheets, generar_id, leer_datos_seguro

# --- CONFIGURACIÓN ---
HOJA_RECETAS = "DB_RECETAS"
HOJA_INSUMOS = "DB_INSUMOS"
HOJA_MENU = "DB_MENU_LOYVERSE"

TOKEN_RESPALDO = "2af9f2845c0b4417925d357b63cfab86"
try:
    LOYVERSE_TOKEN = st.secrets["LOYVERSE_TOKEN"]
except:
    LOYVERSE_TOKEN = TOKEN_RESPALDO

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return str(valor)

# --- BACKEND ---
def cargar_datos(sheet):
    try:
        # 1. INSUMOS
        ws_insumos = sheet.worksheet(HOJA_INSUMOS)
        df_insumos = pd.DataFrame(ws_insumos.get_all_records())
        
        # 2. RECETAS
        ws_recetas = sheet.worksheet(HOJA_RECETAS)
        matriz = ws_recetas.get_all_values()
        
        if len(matriz) > 1:
            df_raw = pd.DataFrame(matriz[1:]) 
            if df_raw.shape[1] >= 5:
                df_recetas = df_raw.iloc[:, [1, 2, 3, 4]].copy()
                df_recetas.columns = ["Nombre_Plato", "ID_Insumo", "Ingrediente", "Cantidad"]
            else:
                df_recetas = pd.DataFrame(columns=["Nombre_Plato", "ID_Insumo", "Ingrediente", "Cantidad"])
        else:
            df_recetas = pd.DataFrame(columns=["Nombre_Plato", "ID_Insumo", "Ingrediente", "Cantidad"])

        # 3. MENÚ LOYVERSE (LECTURA AGRESIVA)
        try:
            ws_menu = sheet.worksheet(HOJA_MENU)
            matriz_menu = ws_menu.get_all_values()
            
            if len(matriz_menu) > 1:
                # Intentamos detectar columnas por nombre, si falla, usamos posición
                headers = [str(h).lower() for h in matriz_menu[0]]
                
                # Buscamos índices (0, 1, 2...) donde estén los datos clave
                # ID: busca "id" o "variant"
                idx_id = next((i for i, h in enumerate(headers) if "id" in h or "variant" in h), 0)
                # Nombre: busca "nombre" o "item" o "producto"
                idx_nom = next((i for i, h in enumerate(headers) if "nombre" in h or "item" in h or "producto" in h), 1)
                # Precio: busca "precio" or "price"
                idx_precio = next((i for i, h in enumerate(headers) if "precio" in h or "price" in h), 2)
                
                datos_limpios = []
                for fila in matriz_menu[1:]:
                    # Asegurar que la fila tenga datos suficientes
                    if len(fila) > max(idx_id, idx_nom, idx_precio):
                        datos_limpios.append({
                            "ID_Variante": fila[idx_id],
                            "Nombre_Producto": fila[idx_nom],
                            "Precio": fila[idx_precio]
                        })
                
                df_menu = pd.DataFrame(datos_limpios)
            else:
                df_menu = pd.DataFrame(columns=["Nombre_Producto", "ID_Variante", "Precio"])
                
        except Exception as e:
            # st.error(f"Error leyendo menú: {e}") # Ocultamos error visual
            df_menu = pd.DataFrame(columns=["Nombre_Producto"])

        return df_insumos, df_recetas, df_menu, ws_recetas

    except Exception as e:
        st.error(f"Error general: {e}")
        return None, None, None, None

def guardar_ingrediente(sheet, datos):
    try:
        ws = sheet.worksheet(HOJA_RECETAS)
        ws.append_row(datos)
        return True
    except: return False

def borrar_ingrediente_receta(sheet, plato, ingrediente):
    try:
        ws = sheet.worksheet(HOJA_RECETAS)
        rows = ws.get_all_values()
        for i, row in enumerate(rows):
            if i == 0: continue 
            if len(row) > 3 and row[1] == plato and row[3] == ingrediente:
                ws.delete_rows(i + 1)
                return True
        return False
    except: return False

def actualizar_loyverse_completo(variant_id, nuevo_precio, nuevo_costo):
    url = f"https://api.loyverse.com/v1.0/variants/{variant_id}"
    headers = {
        "Authorization": f"Bearer {LOYVERSE_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "variant_id": variant_id,
        "default_price": float(nuevo_precio),
        "cost": float(nuevo_costo)
    }
    
    try:
        r = requests.post("https://api.loyverse.com/v1.0/variants", headers=headers, json=payload)
        if r.status_code == 200: return True, "Precio y Costo actualizados."
        
        r2 = requests.put(url, headers=headers, json=payload)
        if r2.status_code == 200: return True, "Precio y Costo actualizados."
        
        return False, f"Error Loyverse: {r.text}"
    except Exception as e:
        return False, str(e)

# --- FRONTEND ---
def show(sheet):
    st.title("👨‍🍳 Ingeniería de Menú")
    
    if not sheet: return

    df_insumos, df_recetas, df_menu, ws_recetas = cargar_datos(sheet)
    if df_insumos is None: return

    # --- FUSIÓN DE LISTAS ---
    # Unimos lo que hay en Loyverse (df_menu) con lo que hay en Recetas locales (df_recetas)
    set_platos = set()
    
    if not df_menu.empty:
        set_platos.update(df_menu["Nombre_Producto"].dropna().tolist())
        
    if not df_recetas.empty:
        set_platos.update(df_recetas["Nombre_Plato"].dropna().tolist())
    
    lista_platos = sorted(list(set_platos))
    
    # Remover vacíos si los hay
    lista_platos = [x for x in lista_platos if str(x).strip() != ""]
    
    col_sel, _ = st.columns([2, 1])
    plato_sel = col_sel.selectbox("🔍 Buscar Plato / Producto:", lista_platos)

    if plato_sel:
        st.markdown("---")
        col_izq, col_der = st.columns([1.5, 1])
        
        # --- DATOS RECETA ---
        receta_actual = pd.DataFrame()
        if not df_recetas.empty:
            receta_actual = df_recetas[df_recetas["Nombre_Plato"] == plato_sel].copy()
        
        costo_total_plato = 0
        detalle_costos = []
        
        if not receta_actual.empty:
            for _, row in receta_actual.iterrows():
                id_ins = row.get("ID_Insumo", "")
                nom_ins = row.get("Ingrediente", "")
                try: cant = float(str(row.get("Cantidad", 0)).replace(",", "."))
                except: cant = 0
                
                info_insumo = pd.DataFrame()
                if id_ins: info_insumo = df_insumos[df_insumos["ID_Insumo"] == id_ins]
                if info_insumo.empty: info_insumo = df_insumos[df_insumos["Nombre_Insumo"] == nom_ins]
                
                costo_unit = 0
                unidad = "N/A"
                if not info_insumo.empty:
                    try: costo_unit = float(str(info_insumo.iloc[0]["Costo_Promedio_Ponderado"]).replace(",", "."))
                    except: costo_unit = 0
                    unidad = info_insumo.iloc[0].get("Unidad_Compra", "Unid")

                costo_linea = costo_unit * cant
                costo_total_plato += costo_linea
                
                detalle_costos.append({
                    "Ingrediente": nom_ins, "Cantidad": cant, "Unidad": unidad, "Costo Total": costo_linea
                })

        # --- DATOS LOYVERSE ---
        precio_loyverse = 0
        variant_id = None
        
        if not df_menu.empty:
            # Buscar coincidencia exacta
            item_data = df_menu[df_menu["Nombre_Producto"] == plato_sel]
            if not item_data.empty:
                try: 
                    precio_loyverse = float(str(item_data.iloc[0]["Precio"]).replace(",", "."))
                    variant_id = str(item_data.iloc[0]["ID_Variante"])
                except: pass

        # --- IZQUIERDA ---
        with col_izq:
            st.subheader(f"🛠️ Receta: {plato_sel}")
            if detalle_costos:
                st.dataframe(pd.DataFrame(detalle_costos), use_container_width=True, hide_index=True)
                
                c_d1, c_d2 = st.columns([3, 1])
                ing_del = c_d1.selectbox("Borrar Ingrediente", ["Seleccionar..."] + [x["Ingrediente"] for x in detalle_costos])
                if ing_del != "Seleccionar..." and c_d2.button("🗑️"):
                    if borrar_ingrediente_receta(sheet, plato_sel, ing_del): st.rerun()
            else:
                st.info("Sin ingredientes.")

            with st.expander("➕ Agregar Ingrediente"):
                if not df_insumos.empty:
                    nuevo_ins = st.selectbox("Insumo", df_insumos["Nombre_Insumo"].tolist())
                    nuevo_cant = st.number_input("Cantidad", min_value=0.0, step=0.1)
                    if st.button("Agregar"):
                        datos_ins = df_insumos[df_insumos["Nombre_Insumo"] == nuevo_ins].iloc[0]
                        fila = [f"REC-{generar_id()}", plato_sel, datos_ins["ID_Insumo"], nuevo_ins, nuevo_cant]
                        if guardar_ingrediente(sheet, fila): st.rerun()

        # --- DERECHA ---
        with col_der:
            st.info(f"📊 **Análisis Financiero**")
            
            c1, c2 = st.columns(2)
            c1.metric("Costo Real", formato_moneda(costo_total_plato))
            c2.metric("Precio Venta", formato_moneda(precio_loyverse))
            
            margen = 0
            if precio_loyverse > 0:
                margen = ((precio_loyverse - costo_total_plato) / precio_loyverse) * 100
            
            st.metric("Margen", f"{margen:.1f}%", delta_color="normal" if margen > 30 else "inverse")

            st.markdown("---")
            st.write("🎯 **Simulador**")
            meta = st.slider("Meta (%)", 10, 90, 35)
            sugerido = costo_total_plato / (1 - (meta/100)) if costo_total_plato > 0 else 0
            st.write(f"Sugerido: **{formato_moneda(sugerido)}**")
            
            if variant_id:
                st.markdown("---")
                col_upd_btn, col_upd_val = st.columns([1, 1.5])
                nuevo_precio = col_upd_val.number_input("Nuevo Precio", value=int(sugerido), step=500)
                
                if col_upd_btn.button("🚀 ACTUALIZAR"):
                    with st.spinner("Enviando..."):
                        ok, msg = actualizar_loyverse_completo(variant_id, nuevo_precio, costo_total_plato)
                        if ok: st.success("✅ ¡Actualizado!")
                        else: st.error(msg)
            else:
                # Si no encuentra el ID, ofrecemos sincronizar
                st.warning("Producto desconectado.")
                if st.button("🔄 Sincronizar Menú"):
                    import subprocess
                    subprocess.run(["python", "sincronizar_loyverse.py"])
                    st.rerun()