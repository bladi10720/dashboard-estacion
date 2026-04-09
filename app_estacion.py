import streamlit as st
import pandas as pd

# 1. CONFIGURACIÓN DE LA PÁGINA
st.set_page_config(page_title="Dashboard de Ventas - Estación", layout="wide")

# 2. TU TABLA DE COMISIONES (Actualiza los códigos y montos aquí)
# El código debe ir entre comillas para evitar errores
TABLA_COMISIONES = {
    "101": 5.0,        
    "102": 7.5,
    "1050": 15.0,      # Ejemplo para Limpiaparabrisas
    "2020": 10.0,      # Ejemplo para otro producto
    # Agrega aquí todos los que necesites siguiendo el mismo formato
}

st.title("⛽ Dashboard de Liquidación de Ventas")

# 3. CARGA DE ARCHIVO
uploaded_file = st.file_provider = st.file_uploader("Cargar reporte de ventas (Excel)", type=["xlsx"])

if uploaded_file:
    # Leer el Excel
    df = pd.read_excel(uploaded_file)
    
    # --- PROCESAMIENTO DE DATOS ---
    
    # Aseguramos que las columnas necesarias existan (ajusta si cambian en tu Excel)
    columnas_necesarias = ['cod Producto', 'Descripcion', 'Cantidad', 'Cajero']
    
    if all(col in df.columns for col in columnas_necesarias):
        
        # Limpieza de datos crítica
        df['cod Producto'] = df['cod Producto'].astype(str).str.strip()
        df['Descripcion'] = df['Descripcion'].astype(str).str.strip()
        
        # Crear columna combinada para que tú la veas clara
        df['Producto_Info'] = df['cod Producto'] + " - " + df['Descripcion']
        
        # --- CÁLCULO DE COMISIONES ---
        # Si el código no está en la tabla, la comisión es 0
        df['Pago_Comision'] = df.apply(
            lambda x: x['Cantidad'] * TABLA_COMISIONES.get(x['cod Producto'], 0), axis=1
        )
        
        # --- FILTROS EN LA BARRA LATERAL ---
        st.sidebar.header("Filtros")
        
        cajeros = df['Cajero'].unique()
        cajero_sel = st.sidebar.multiselect("Seleccionar Cajero:", options=cajeros, default=cajeros)
        
        productos = df['Producto_Info'].unique()
        prod_sel = st.sidebar.multiselect("Seleccionar Producto:", options=productos, default=productos)
        
        # Aplicar Filtros
        df_filtrado = df[(df['Cajero'].isin(cajero_sel)) & (df['Producto_Info'].isin(prod_sel))]
        
        # --- VISUALIZACIÓN DE RESULTADOS ---
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_unidades = df_filtrado['Cantidad'].sum()
            st.metric("Total Unidades/Litros", f"{total_unidades:,.2f}")
            
        with col2:
            total_comisiones = df_filtrado['Pago_Comision'].sum()
            st.metric("Total Comisiones a Pagar", f"$ {total_comisiones:,.0f}")
            
        with col3:
            st.metric("N° de Transacciones", len(df_filtrado))
            
        # Tabla resumen por Cajero
        st.subheader("💰 Resumen de Comisiones por Cajero")
        resumen_cajero = df_filtrado.groupby('Cajero')['Pago_Comision'].sum().reset_index()
        st.dataframe(resumen_cajero, use_container_width=True)
        
        # Detalle completo
        st.subheader("📋 Detalle de Ventas")
        st.dataframe(df_filtrado[['Cajero', 'Producto_Info', 'Cantidad', 'Pago_Comision']], use_container_width=True)
        
    else:
        st.error(f"Error: El archivo debe contener las columnas: {columnas_necesarias}")
else:
    st.info("Esperando archivo Excel... Por favor, cárgalo en la parte superior.")