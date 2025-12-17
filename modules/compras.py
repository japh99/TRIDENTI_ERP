import streamlit as st
import pandas as pd
import time
from datetime import datetime
import pytz 
from utils import leer_datos_seguro, limpiar_numero, generar_id, subir_foto_drive, limpiar_cache

ZONA_CO = pytz.timezone('America/Bogota')

def show(sheet):
    st.header("🛒 Registro de Compras")
    
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

    if df_insumos.empty or "Nombre_Insumo" not in df_insumos.columns:
        st.warning("⚠️ Crea insumos primero.")
        return

    tab_registro, tab_deudas = st.tabs(["📝 REGISTRAR COMPRA", "💸 CUENTAS POR PAGAR"])

    with tab_registro:
        c1, c2, c3 = st.columns(3)
        fecha = c1.date_input("Fecha Factura", value=datetime.now(ZONA_CO).date())
        proveedor = c2.selectbox("Proveedor", lista_proveedores)
        factura = c3.text_input("N° Factura")
        
        pago = st.radio("Método de Pago:", ["Efectivo", "Transferencia/Nequi", "Crédito (Deuda)"], horizontal=True)
        estado_inicial = "Pendiente" if "Crédito" in pago else "Pagado"

        st.markdown("---")

        lista_ins = df_insumos['Nombre_Insumo'].astype(str) + " | " + df_insumos['ID_Insumo'].astype(str)
        insumo_sel = st.selectbox("📦 PRODUCTO COMPRADO:", lista_ins)
        
        if insumo_sel:
            id_insumo = insumo_sel.split(" | ")[1]
            info_ins = df_insumos[df_insumos['ID_Insumo'] == id_insumo].iloc[0]
            costo_actual_bd = limpiar_numero(info_ins.get('Costo_Promedio_Ponderado', 0))
            
            # --- CANTIDADES ---
            st.write("### 📏 Cantidad Comprada")
            tipo_medida = st.radio("Unidad:", ["PESO (Gr/Kg)", "VOLUMEN (Ml/Lt)", "UNIDADES (Paquetes)"], horizontal=True)
            
            factor_entrada = 0.0
            txt_unidad = ""
            c_izq, c_der = st.columns(2)
            
            if tipo_medida == "PESO (Gr/Kg)":
                with c_izq: uni = st.selectbox("Presentación", ["Kilo (1000g)", "Libra (500g)", "Bulto (50kg)", "Bulto (25kg)", "Gramo"])
                with c_der: cant = st.number_input("Cantidad", 0.0, step=0.5)
                base = 1000
                if "Libra" in uni: base = 500
                elif "50kg" in uni: base = 50000
                elif "25kg" in uni: base = 25000
                elif "Gramo" in uni: base = 1
                factor_entrada = base * cant
                txt_unidad = uni
                
            elif tipo_medida == "VOLUMEN (Ml/Lt)":
                with c_izq: uni = st.selectbox("Presentación", ["Litro", "Galón (3.75L)", "Botella (750ml)", "Ml"])
                with c_der: cant = st.number_input("Cantidad", 0.0, step=0.5)
                base = 1000
                if "Galón" in uni: base = 3785
                elif "Botella" in uni: base = 750
                elif "Ml" in uni: base = 1
                factor_entrada = base * cant
                txt_unidad = uni
                
            elif tipo_medida == "UNIDADES (Paquetes)":
                with c_izq: es_pack = st.selectbox("Tipo", ["Paquete / Caja", "Unidad Suelta"])
                if "Paquete" in es_pack:
                    with c_izq: u_pack = st.number_input("Unds por Paquete", 1, step=1)
                    with c_der: cant = st.number_input("Cant. Paquetes", 0, step=1)
                    factor_entrada = u_pack * cant
                    txt_unidad = f"Paquete x{u_pack}"
                else:
                    with c_der: cant = st.number_input("Total Unidades", 0, step=1)
                    factor_entrada = cant
                    txt_unidad = "Unidad Suelta"

            # --- SECCIÓN DE MERMA REAL (AQUÍ ESTÁ LA MEJORA) ---
            st.markdown("### 📉 Control de Merma (Limpieza)")
            tiene_merma = st.checkbox("¿Este producto requiere limpieza/desperdicio inicial?")
            
            merma_pct = 0.0
            cantidad_util = factor_entrada
            
            if tiene_merma:
                merma_pct = st.slider("% de Desperdicio (Grasa, Cáscara, etc.)", 0, 80, 15)
                cantidad_util = factor_entrada * (1 - (merma_pct/100))
                st.caption(f"💡 Compraste **{factor_entrada:,.0f}**, pero realmente usarás **{cantidad_util:,.0f}**.")

            st.markdown("---")
            
            # --- PRECIO ---
            c_money, c_foto = st.columns(2)
            precio = c_money.number_input("💰 Precio TOTAL Factura ($)", 0.0, step=1000.0)
            foto = c_foto.file_uploader("📸 Foto Factura")

            # CÁLCULO DE COSTO REAL (CON MERMA)
            # El costo se distribuye solo en la parte útil del producto
            nuevo_costo_real = 0.0
            if precio > 0 and cantidad_util > 0:
                nuevo_costo_real = precio / cantidad_util
            
            st.info(f"📊 Costo Real por Unidad/Gramo (Inc. Merma): **${nuevo_costo_real:,.1f}**")
            
            if nuevo_costo_real > costo_actual_bd * 1.1 and costo_actual_bd > 0:
                st.warning(f"⚠️ ¡OJO! El costo subió más del 10% vs el promedio anterior (${costo_actual_bd:,.1f}).")

            if st.button("💾 GUARDAR COMPRA", type="primary"):
                if precio > 0 and factor_entrada > 0:
                    with st.spinner("Guardando..."):
                        link = "Sin Foto"
                        if foto: link = subir_foto_drive(foto)
                        
                        if "Error" in link:
                            st.error(f"❌ {link}")
                        else:
                            stock_now = limpiar_numero(info_ins.get('Stock_Actual_Gr', 0))
                            # Sumamos al inventario SOLO LO ÚTIL (La merma se bota)
                            new_stock = stock_now + cantidad_util
                            
                            id_compra = f"BUY-{generar_id()}"
                            
                            log = [id_compra, str(fecha), proveedor, id_insumo, info_ins['Nombre_Insumo'],
                                   factor_entrada, txt_unidad, precio, nuevo_costo_real, link, 
                                   factura, pago, estado_inicial, f"Merma: {merma_pct}%"] 
                            
                            hoja_log.append_row(log)
                            
                            try:
                                cell = hoja_insumos.find(id_insumo)
                                # Actualizar Stock (Col 7)
                                hoja_insumos.update_cell(cell.row, 7, new_stock)
                                
                                # Actualizar Costo Promedio (Col 9)
                                # Aquí podríamos hacer un promedio ponderado real, pero por ahora actualizamos al último real
                                hoja_insumos.update_cell(cell.row, 9, nuevo_costo_real)
                                
                                # Actualizar Costo Ultima Compra (Col 6) - Guardamos el precio del paquete completo
                                # Para referencia futura en sugeridos
                                hoja_insumos.update_cell(cell.row, 6, precio) 
                                
                            except: pass
                            
                            st.success(f"✅ Compra registrada. Stock Útil: {new_stock:,.0f}")
                            limpiar_cache()
                            time.sleep(1)
                            st.rerun()
                else:
                    st.error("⚠️ Faltan datos.")

    with tab_deudas:
        st.write("### 💸 Cuentas por Pagar")
        df_log = leer_datos_seguro(hoja_log)
        
        if not df_log.empty and 'Estado_Pago' in df_log.columns:
            deudas = df_log[df_log['Estado_Pago'] == 'Pendiente'].copy()
            if not deudas.empty:
                deudas['Precio_Total_Pagado'] = pd.to_numeric(deudas['Precio_Total_Pagado'], errors='coerce')
                st.error(f"🔴 DEUDA TOTAL: **${deudas['Precio_Total_Pagado'].sum():,.0f}**")
                st.dataframe(deudas[['Fecha_Registro', 'Proveedor', 'Nombre_Insumo', 'Precio_Total_Pagado']], use_container_width=True, hide_index=True)
                
                # Pago simple
                pagar = st.selectbox("Pagar:", deudas['ID_Compra'].tolist())
                if st.button("Pagar Deuda"):
                    cell = hoja_log.find(pagar)
                    hoja_log.update_cell(cell.row, 13, "Pagado")
                    st.success("Pagado")
                    time.sleep(1)
                    st.rerun()
            else: st.success("🎉 Paz y salvo.")