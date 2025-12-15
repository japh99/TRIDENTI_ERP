import streamlit as st
import pandas as pd
import time
from datetime import datetime
import pytz # Importamos Zona Horaria
from utils import leer_datos_seguro, limpiar_numero, generar_id, subir_foto_drive, limpiar_cache

# --- CONFIGURACIÓN DE ZONA HORARIA ---
ZONA_CO = pytz.timezone('America/Bogota')

def show(sheet):
    st.header("🛒 Registro de Compras")
    
    # 1. CARGA DE DATOS
    try:
        hoja_insumos = sheet.worksheet("DB_INSUMOS")
        hoja_log = sheet.worksheet("LOG_COMPRAS")
        df_insumos = leer_datos_seguro(hoja_insumos)
        
        try:
            hoja_prov = sheet.worksheet("DB_PROVEEDORES")
            df_prov = leer_datos_seguro(hoja_prov)
            lista_proveedores = df_prov['Nombre_Empresa'].unique().tolist()
        except:
            lista_proveedores = ["General"]
    except: return

    # TABS
    tab_registro, tab_deudas = st.tabs(["📝 REGISTRAR COMPRA", "💸 CUENTAS POR PAGAR"])

    with tab_registro:
        # --- AQUÍ ESTÁ EL ARREGLO: NO USAMOS st.form PARA LOS CAMPOS ---
        
        c1, c2, c3 = st.columns(3)
        # Fecha con hora colombiana
        fecha_colombia = datetime.now(ZONA_CO).date()
        fecha = c1.date_input("Fecha Factura", value=fecha_colombia)
        
        proveedor = c2.selectbox("Proveedor", lista_proveedores)
        factura = c3.text_input("N° Factura", placeholder="Opcional")
        
        pago = st.radio("Método de Pago:", ["Efectivo", "Transferencia/Nequi", "Crédito (Deuda)"], horizontal=True)
        estado_inicial = "Pendiente" if "Crédito" in pago else "Pagado"

        st.markdown("---")

        # 2. PRODUCTO
        lista_ins = df_insumos['Nombre_Insumo'] + " | " + df_insumos['ID_Insumo']
        insumo_sel = st.selectbox("📦 PRODUCTO A COMPRAR:", lista_ins)
        
        id_insumo = insumo_sel.split(" | ")[1]
        info_ins = df_insumos[df_insumos['ID_Insumo'] == id_insumo].iloc[0]
        costo_actual_bd = limpiar_numero(info_ins.get('Costo_Promedio_Ponderado', 0))
        
        # 3. MEDIDAS (INTERACTIVO - SIN FANTASMAS)
        st.write("### 📏 Configuración de Entrada")
        # Al no estar en un form, este radio actualiza la pantalla al instante
        tipo_medida = st.radio("¿Cómo viene en la factura?", ["PESO (Gr/Kg)", "VOLUMEN (Ml/Lt)", "UNIDADES (Paquetes)"], horizontal=True)
        
        factor_entrada = 0.0
        txt_unidad = ""
        c_izq, c_der = st.columns(2)
        
        # LÓGICA DINÁMICA
        if tipo_medida == "PESO (Gr/Kg)":
            with c_izq: uni = st.selectbox("Unidad", ["Kilo (1000g)", "Libra (500g)", "Bulto (50kg)", "Bulto (25kg)", "Gramo"])
            with c_der: cant = st.number_input("Cantidad Peso", 0.0, step=0.5)
            base = 1000
            if "Libra" in uni: base = 500
            elif "Bulto (50" in uni: base = 50000
            elif "Bulto (25" in uni: base = 25000
            elif "Gramo" in uni: base = 1
            factor_entrada = base * cant
            txt_unidad = uni
            
        elif tipo_medida == "VOLUMEN (Ml/Lt)":
            with c_izq: uni = st.selectbox("Unidad", ["Litro", "Galón (3.75L)", "Botella (750ml)", "Ml"])
            with c_der: cant = st.number_input("Cantidad Volumen", 0.0, step=0.5)
            base = 1000
            if "Galón" in uni: base = 3785
            elif "Botella" in uni: base = 750
            elif "Ml" in uni: base = 1
            factor_entrada = base * cant
            txt_unidad = uni
            
        elif tipo_medida == "UNIDADES (Paquetes)":
            with c_izq: es_pack = st.selectbox("Presentación", ["Paquete / Caja", "Unidad Suelta"])
            if "Paquete" in es_pack:
                with c_izq: u_pack = st.number_input("¿Unidades por Paquete?", 1, step=1)
                with c_der: cant = st.number_input("¿Cuántos Paquetes?", 0, step=1)
                factor_entrada = u_pack * cant
                txt_unidad = f"Paquete x{u_pack}"
            else:
                with c_der: cant = st.number_input("Total Unidades Sueltas", 0, step=1)
                factor_entrada = cant
                txt_unidad = "Unidad Suelta"

        st.markdown("---")
        
        # 4. PRECIO
        c_money, c_foto = st.columns(2)
        precio = c_money.number_input("💰 Precio TOTAL Factura ($)", 0.0, step=1000.0)
        foto = c_foto.file_uploader("📸 Foto Factura")

        nuevo_costo = 0.0
        if precio > 0 and factor_entrada > 0:
            nuevo_costo = precio / factor_entrada
        
        # AUDITORÍA DE PRECIOS
        st.write("### 📊 Auditoría de Precios")
        k1, k2, k3 = st.columns(3)
        k1.metric("Costo Anterior", f"${costo_actual_bd:,.2f}")
        k2.metric("Nuevo Costo", f"${nuevo_costo:,.2f}")
        diff = nuevo_costo - costo_actual_bd
        k3.metric("Variación", f"${diff:,.2f}", delta_color="inverse")
        
        if estado_inicial == "Pendiente":
            st.warning(f"⚠️ Compra a CRÉDITO.")

        act_precio = st.checkbox("✅ ACTUALIZAR PRECIO EN SISTEMA", value=True)

        # BOTÓN FINAL (Este es el único que envía datos)
        if st.button("💾 REGISTRAR COMPRA", type="primary"):
            if precio > 0 and factor_entrada > 0:
                with st.spinner("Guardando..."):
                    link = "Sin Foto"
                    if foto: link = subir_foto_drive(foto)
                    
                    if "Error" in link:
                        st.error(f"❌ {link}")
                    else:
                        stock_now = limpiar_numero(info_ins.get('Stock_Actual_Gr', 0))
                        new_stock = stock_now + factor_entrada
                        
                        id_compra = f"BUY-{generar_id()}"
                        # Guardar con fecha colombiana
                        log = [id_compra, str(fecha), proveedor, id_insumo, info_ins['Nombre_Insumo'],
                               factor_entrada, txt_unidad, precio, nuevo_costo, link, 
                               factura, pago, estado_inicial, ""] 
                        
                        hoja_log.append_row(log)
                        
                        cell = hoja_insumos.find(id_insumo)
                        hoja_insumos.update_cell(cell.row, 7, new_stock)
                        
                        if act_precio:
                            hoja_insumos.update_cell(cell.row, 6, precio)
                            hoja_insumos.update_cell(cell.row, 9, nuevo_costo)
                        
                        st.success(f"✅ Compra registrada. Stock: {new_stock:,.0f}")
                        limpiar_cache()
                        time.sleep(1)
                        st.rerun()
            else:
                st.error("⚠️ Faltan datos.")

    # PESTAÑA 2: DEUDAS (Código Igual...)
    with tab_deudas:
        st.write("### 💸 Cuentas por Pagar")
        df_log = leer_datos_seguro(hoja_log)
        
        if not df_log.empty and 'Estado_Pago' in df_log.columns:
            deudas = df_log[df_log['Estado_Pago'] == 'Pendiente'].copy()
            if not deudas.empty:
                deudas['Precio_Total_Pagado'] = pd.to_numeric(deudas['Precio_Total_Pagado'])
                total_deuda = deudas['Precio_Total_Pagado'].sum()
                st.error(f"🔴 DEUDA TOTAL: **${total_deuda:,.0f}**")
                
                st.dataframe(deudas[['Fecha_Registro', 'Proveedor', 'Nombre_Insumo', 'Precio_Total_Pagado']], use_container_width=True, hide_index=True)
                
                st.markdown("---")
                c_sel, c_met = st.columns(2)
                lista_pagar = deudas['Proveedor'] + " - $" + deudas['Precio_Total_Pagado'].astype(str) + " (" + deudas['ID_Compra'] + ")"
                factura_a_pagar = c_sel.selectbox("Pagar Factura:", lista_pagar)
                medio_pago_deuda = c_met.selectbox("Medio de Pago:", ["Transferencia", "Nequi", "Efectivo"])
                
                if st.button("✅ REGISTRAR PAGO"):
                    id_buscar = factura_a_pagar.split("(")[1].replace(")", "")
                    try:
                        celda = hoja_log.find(id_buscar)
                        hoja_log.update_cell(celda.row, 13, "Pagado")
                        hoja_log.update_cell(celda.row, 14, f"{medio_pago_deuda} ({datetime.now(ZONA_CO).date()})")
                        st.success("✅ ¡Deuda saldada!")
                        limpiar_cache()
                        time.sleep(1)
                        st.rerun()
                    except: st.error("Error al pagar")
            else: st.success("🎉 ¡Estás al día!")
        else: st.info("Sin historial.")