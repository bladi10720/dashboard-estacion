import streamlit as st
import pandas as pd

st.set_page_config(page_title="Dashboard Estación Pro", layout="wide")

# 1. TABLA DE COMISIONES (Aquí pones tus códigos o nombres)
TABLA_COMISIONES = {
    "101": 5.0,
    "102": 7.5,
    "LIMPIAPARABRISAS": 15.0,
    "1050": 15.0,
}

st.title("⛽ Gestión de Ventas y Comisiones")

# 2. CARGA MÚLTIPLE ACTIVADA
uploaded_files = st.file_uploader("Sube uno o varios archivos Excel", type=["xlsx"], accept_multiple_files=True)

if uploaded_files:
    lista_df = []
    for file in uploaded_files:
        temp_df = pd.read_excel(file)
        lista_df.append(temp_df)
    
    # Unimos todos los archivos en uno solo
    df = pd.concat(lista_df, ignore_index=True)
    
    # --- LIMPIEZA AUTOMÁTICA DE COLUMNAS ---
    # Esto quita espacios y asegura que Python encuentre "Cajero" aunque diga " cajero "
    df.columns = [str(c).strip() for c in df.columns]

    # --- LÓGICA DE CÁLCULO FLEXIBLE ---
    # Buscamos cuál columna existe para trabajar
    col_producto = 'cod Producto' if 'cod Producto' in df.columns else 'Descripcion'
    
    if col_producto in df.columns and 'Cantidad' in df.columns:
        # Limpiamos los datos de la columna seleccionada
        df[col_producto] = df[col_producto].astype(str).str.strip()
        
        # Calculamos comisiones (Si es por código o por nombre, el sistema lo busca en la tabla)
        df['Pago_Comision'] = df.apply(
            lambda x: x['Cantidad'] * TABLA_COMISIONES.get(x[col_producto].upper() if col_producto == 'Descripcion' else x[col_producto], 0), axis=1
        )
        
        # --- FILTROS ---
        st.sidebar.header("Filtros Rápidos")
        
        # Filtro de Cajeros (si existe la columna)
        if 'Cajero' in df.columns:
            cajeros = st.sidebar.multiselect("Filtrar por Cajero:", options=df['Cajero'].unique(), default=df['Cajero'].unique())
            df = df[df['Cajero'].isin(cajeros)]

        # --- MÉTRICAS PRINCIPALES ---
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Litros/Unidades", f"{df['Cantidad'].sum():,.2f}")
        c2.metric("Comisiones Totales", f"$ {df['Pago_Comision'].sum():,.0f}")
        c3.metric("Ventas Procesadas", len(df))

        # --- TABLAS DE RESULTADOS ---
        st.subheader("📊 Resumen por Producto")
        resumen = df.groupby(col_producto).agg({'Cantidad': 'sum', 'Pago_Comision': 'sum'}).reset_index()
        st.dataframe(resumen, use_container_width=True)
        
        st.subheader("📝 Detalle General")
        st.dataframe(df, use_container_width=True)
    else:
        st.warning(f"El archivo debe tener al menos las columnas 'Cantidad' y '{col_producto}'")
else:
    st.info("Carga tus archivos de ventas para empezar.")