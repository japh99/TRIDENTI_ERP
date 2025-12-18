import streamlit as st
import pandas as pd
from datetime import datetime
import uuid
import time
from utils import conectar_google_sheets, leer_datos_seguro, generar_id, limpiar_numero, ZONA_HORARIA

# --- CONFIGURACIÓN ---
HOJA_SUBRECETAS = "DB_SUBRECETAS"
HOJA_INSUMOS = "DB_INSUMOS"
HOJA_KARDEX = "KARDEX_MOVIMIENTOS"

def formato_moneda(valor):
    if pd.isna(valor) or valor == "": return "$ 0"
    try: return f"$ {int(float(valor)):,}".replace(",", ".")
    except: return "$ 0"

def cargar_datos_produccion(sheet):
    """Carga insumos y las fórmulas de subrecetas."""
    try:
        ws_ins = sheet.worksheet(HOJA_INSUMOS)
        df_ins = pd.DataFrame(ws_ins.get_all_records())
        
        # Intentar cargar subrecetas (Crea la hoja si no existe)
        try:
            ws_sub = sheet.worksheet(HOJA_SUBRECETAS)
            matriz = ws_sub.get_all_values()
            if len(matriz) > 1:
                df_sub = pd.DataFrame(matriz[1:], columns=matriz[0])
                # Asegurar columnas correctas
                if len(df_sub.columns) >= 3:
                    df_sub = df_sub.iloc[:, [0, 1, 2]]
                    df_sub.columns = ["Nombre_Subreceta", "Insumo_Base", "Cantidad_Base"]
            else: df_sub = pd.DataFrame(columns=["Nombre_Subreceta", "Insumo_Base", "Cantidad_Base"])
        except:
            ws_sub = sheet.add_worksheet(title=HOJA_SUBRECETAS, rows="1000", cols="5")
            ws_sub.append_row(["Nombre_Subreceta", "Insumo_Base", "Cantidad_Base"])
            df_sub = pd.DataFrame(columns=["Nombre_Subreceta", "Insumo_Base", "Cantidad_Base"])

        return df_ins, df_sub, ws_ins, ws_sub
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return None, None, None, None

def guardar_item_subreceta(sheet, datos):
    """Guarda un ingrediente de la fórmula."""
    try:
        ws = sheet.worksheet(HOJA_SUBRECETAS)
        ws.append_row(datos)
        return True
    except: return False

def crear_o_actualizar_insumo_derivado(ws_insumos, df_insumos, nombre_subreceta, unidad, costo_unitario):
    """
    MAGIA: Convierte la Sub-receta en un INSUMO REAL para que aparezca en el inventario.
    """
    try:
        # Buscar si ya existe este "Insumo Preparado"
        existe = df_insumos[df_insumos["Nombre_Insumo"] == nombre_subreceta]
        
        if not existe.empty:
            # Si existe, actualizamos su costo promedio (Columna I = 9)
            # IMPORTANTE: Buscamos la fila exacta usando el ID para no fallar
            id_insumo = existe.iloc[0]["ID_Insumo"]
            cell = ws_insumos.find(id_insumo)
            ws_insumos.update_cell(cell.row, 9, costo_unitario) # Actualiza Costo Promedio
            ws_insumos.update_cell(cell.row, 6, costo_unitario) # Actualiza Costo Ultima Compra
            return "Actualizado"
        else:
            # Si no existe, lo creamos como un insumo nuevo
            nuevo_id = f"PREP-{generar_id()}"
            # Estructura 11 columnas: ID, Nombre, Categoria, Unidad, Factor, Costo_Ult, Stock, Min, Costo_Prom, Merma, Prov
            fila_nueva = [
                nuevo_id, 
                nombre_subreceta, 
                "Producción Interna", # Categoría especial
                unidad, 
                1, # Factor 1 (porque se produce en la unidad de consumo)
                costo_unitario, # Costo Ultima
                0, # Stock Inicial
                0, # Minimo
                costo_unitario, # Costo Promedio
                0, # Merma
                "Cocina Interna" # Proveedor
            ]
            ws_insumos.append_row(fila_nueva)
            return "Creado"
    except Exception as e:
        st.error(f"Error creando insumo derivado: {e}")
        return "Error"

def registrar_produccion(sheet, df_insumos, nombre_subreceta, cantidad_producida, lista_ingredientes):
    """
    1. Resta ingredientes (Materia Prima).
    2. Suma producto terminado (Salsa).
    3. Registra en Kardex.
    """
    try:
        ws_insumos = sheet.worksheet(HOJA_INSUMOS)
        ws_kardex = sheet.worksheet(HOJA_KARDEX)
        
        fecha = datetime.now(ZONA_HORARIA).strftime("%Y-%m-%d")
        hora = datetime.now(ZONA_HORARIA).strftime("%H:%M")
        
        logs_kardex = []
        updates_stock = []
        
        # 1. RESTAR INGREDIENTES (Materia Prima)
        costo_total_lote = 0
        
        for ing in lista_ingredientes:
            nombre_ing = ing["Insumo"]
            cant_requerida_unitaria = ing["Cantidad"]
            total_baja = cant_requerida_unitaria * cantidad_producida
            
            # Buscar datos del ingrediente
            datos_ing = df_insumos[df_insumos["Nombre_Insumo"] == nombre_ing]
            if datos_ing.empty: continue
            
            # Leer Stock Actual
            stock_actual = float(str(datos_ing.iloc[0]["Stock_Actual_Gr"]).replace(",", ".") or 0)
            costo_ing = float(str(datos_ing.iloc[0].get("Costo_Promedio_Ponderado", 0)).replace(",", ".") or 0)
            
            # Buscar Fila para actualizar
            id_ing = datos_ing.iloc[0]["ID_Insumo"]
            cell_ing = ws_insumos.find(id_ing)
            
            nuevo_stock = stock_actual - total_baja
            costo_total_lote += (total_baja * costo_ing)
            
            # Preparar update
            updates.append((cell_ing.row, 7, nuevo_stock)) # Col 7 = Stock
            
            # Kardex Salida
            # ID, Fecha, Hora, Tipo, Insumo, Ent, Sal, Saldo, Costo, Detalle
            logs_kardex.append([
                generar_id(), fecha, hora, "SALIDA (PRODUCCIÓN)", 
                nombre_ing, 0, total_baja, nuevo_stock, costo_ing, 
                f"Usado para: {cantidad_producida} de {nombre_subreceta}"
            ])

        # 2. SUMAR PRODUCTO TERMINADO (La Salsa)
        datos_salsa = df_insumos[df_insumos["Nombre_Insumo"] == nombre_subreceta]
        
        if not datos_salsa.empty:
            stock_salsa = float(str(datos_salsa.iloc[0]["Stock_Actual_Gr"]).replace(",", ".") or 0)
            id_salsa = datos_salsa.iloc[0]["ID_Insumo"]
            cell_salsa = ws_insumos.find(id_salsa)
            
            nuevo_stock_salsa = stock_salsa + cantidad_producida
            
            # Calcular nuevo costo unitario real
            costo_unitario_final = costo_total_lote / cantidad_producida if cantidad_producida > 0 else 0
            
            # Update Stock
            updates.append((cell_salsa.row, 7, nuevo_stock_salsa))
            
            # Update Costo (Para que la próxima vez se sepa cuánto costó hacerla)
            # Col 9 = Costo Promedio, Col 6 = Costo Ultima
            ws_insumos.update_cell(cell_salsa.row, 9, costo_unitario_final)
            ws_insumos.update_cell(cell_salsa.row, 6, costo_unitario_final)
            
            # Kardex Entrada
            logs_kardex.append([
                generar_id(), fecha, hora, "ENTRADA (PRODUCCIÓN)", 
                nombre_subreceta, cantidad_producida, 0, nuevo_stock_salsa, costo_unitario_final, 
                "Producción Interna Finalizada"
            ])
            
        # EJECUTAR TODOS LOS CAMBIOS EN BATCH (Uno por uno para seguridad)
        progreso = st.progress(0)
        total_ops = len(updates)
        i = 0
        for fila, col, val in updates:
            ws_insumos.update_cell(fila, col, val)
            i += 1
            progreso.progress(i / total_ops)
            
        ws_kardex.append_rows(logs_kardex)
        return True
        
    except Exception as e:
        st.error(f"Error en producción: {e}")
        return False

# --- INTERFAZ ---
def show(sheet):
    st.title("🥣 Sub-recetas & Producción")
    st.caption("Transforma materia prima en productos listos para usar.")
    st.markdown("---")
    
    if not sheet: return
    
    df_insumos, df_sub, ws_ins, ws_sub = cargar_datos_produccion(sheet)
    if df_insumos is None: return

    tab1, tab2 = st.tabs(["📝 DISEÑAR FÓRMULA", "🔥 COCINAR (PRODUCIR)"])

    # --- TAB 1: CREAR LA RECETA DE LA SALSA ---
    with tab1:
        st.info("Paso 1: Define qué lleva tu preparación (Ej: Salsa Tartara = Mayonesa + Alcaparras).")
        
        c1, c2 = st.columns(2)
        nombres_existentes = sorted(df_insumos["Nombre_Insumo"].unique().tolist())
        
        nombre_sub = c1.text_input("Nombre de la Preparación", placeholder="Ej: Salsa de la Casa")
        unidad_prod = c2.selectbox("Unidad de Medida Final", ["Litro (1000ml)", "Kilo (1000g)", "Porción", "Unidad"])
        
        if nombre_sub:
            st.markdown(f"### 🧪 Ingredientes para: **{nombre_sub}**")
            
            # Ingredientes actuales
            ingredientes_actuales = []
            if not df_sub.empty:
                filtro = df_sub[df_sub["Nombre_Subreceta"] == nombre_sub]
                if not filtro.empty:
                    st.dataframe(filtro[["Insumo_Base", "Cantidad_Base"]], use_container_width=True, hide_index=True)
                    for _, r in filtro.iterrows():
                        ingredientes_actuales.append({"Insumo": r["Insumo_Base"], "Cantidad": float(r["Cantidad_Base"])})

            # Agregar Ingrediente
            with st.container(border=True):
                col_i1, col_i2, col_i3 = st.columns([2, 1, 1])
                insumo_base = col_i1.selectbox("Materia Prima", nombres_existentes)
                cant_base = col_i2.number_input(f"Cantidad necesaria", min_value=0.0, step=0.1, help="Cuánto de este insumo necesito para hacer 1 UNIDAD de la preparación.")
                
                if col_i3.button("➕ Agregar"):
                    if cant_base > 0:
                        if guardar_item_subreceta(sheet, [nombre_sub, insumo_base, cant_base]):
                            st.success("Guardado"); time.sleep(0.5); st.rerun()

            # GUARDAR COMO INSUMO
            if ingredientes_actuales:
                st.markdown("---")
                costo_total = 0
                for item in ingredientes_actuales:
                    dato = df_insumos[df_insumos["Nombre_Insumo"] == item["Insumo"]]
                    if not dato.empty:
                        costo_u = float(str(dato.iloc[0].get("Costo_Promedio_Ponderado", 0)).replace(",", ".") or 0)
                        costo_total += costo_u * item["Cantidad"]
                
                st.metric("Costo Teórico (Materia Prima)", formato_moneda(costo_total))
                
                if st.button("💾 CREAR ESTA PREPARACIÓN EN EL INVENTARIO", type="primary"):
                    with st.spinner("Creando insumo..."):
                        res = crear_o_actualizar_insumo_derivado(ws_ins, df_insumos, nombre_sub, unidad_prod, costo_total)
                        if res in ["Creado", "Actualizado"]:
                            st.balloons()
                            st.success(f"✅ ¡Listo! '{nombre_sub}' ahora es un insumo. Ve a 'Recetas' y úsalo en tus platos.")
                        else: st.error("Error.")

    # --- TAB 2: REGISTRAR QUE SE COCINÓ ---
    with tab2:
        st.subheader("👨‍🍳 Registro de Producción del Día")
        
        if not df_sub.empty:
            lista_subs = sorted(df_sub["Nombre_Subreceta"].unique().tolist())
            sub_sel = st.selectbox("¿Qué prepararon hoy?", lista_subs)
            
            if sub_sel:
                receta_batch = df_sub[df_sub["Nombre_Subreceta"] == sub_sel]
                
                c_p1, c_p2 = st.columns(2)
                cantidad_prod = c_p1.number_input(f"¿Cuánto se hizo?", min_value=0.0, step=1.0, help="Ej: 5 Litros")
                
                if cantidad_prod > 0:
                    st.info(f"📉 Al registrar, se descontará del inventario:")
                    
                    lista_baja = []
                    for _, row in receta_batch.iterrows():
                        base = float(row["Cantidad_Base"])
                        total = base * cantidad_prod
                        lista_baja.append({"Insumo": row["Insumo_Base"], "Cantidad": float(row["Cantidad_Base"]), "Total a Descontar": total})
                    
                    st.dataframe(pd.DataFrame(lista_baja), use_container_width=True)
                    
                    if st.button("🔥 CONFIRMAR PRODUCCIÓN", type="primary"):
                        with st.spinner("Actualizando Kardex..."):
                            if registrar_produccion(sheet, df_insumos, sub_sel, cantidad_prod, lista_baja):
                                st.balloons()
                                st.success(f"✅ Producción registrada. Stock actualizado.")
                                time.sleep(2); st.rerun()
        else:
            st.warning("Crea primero una sub-receta en la pestaña anterior.")