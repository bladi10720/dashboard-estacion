import streamlit as st
import pandas as pd
import plotly.express as px
import io

# =========================================================
# 1. CONFIGURACIÓN DE COMISIONES
# =========================================================
TABLA_COMISIONES = {
    'GASOLINA 93': 5.0,
    'GASOLINA 95': 8.0,
    'GASOLINA 97': 10.0,
    'DIESEL': 4.0,
    'KEROSENE': 6.0,
    'ACEITE MOTOR': 500.0,
    'ADBLUE': 16.0,
    'bidon 20 lt comb gas': 10000,
    'Gasolina 93 octanos': 10000,
    'V-POWER Gasolina 97 ': 10000
}

# =========================================================
# 2. CONFIGURACIÓN DE LA PÁGINA
# =========================================================
st.set_page_config(page_title="Estación Pro - Reportes", layout="wide", page_icon="⛽")

# Estilo CSS para mejorar la apariencia
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    [data-testid="stMetricValue"] { font-size: 28px; color: #004b87; }
    </style>
    """, unsafe_allow_html=True)

st.title("⛽ Sistema de Gestión de Ventas - Estación Pro")

# =========================================================
# 3. CARGA DE DATOS (NUEVO: BOTÓN DE SUBIDA)
# =========================================================
# Este cuadro aparecerá ahora en el centro de tu pantalla
archivos_subidos = st.file_uploader(
    "📂 Selecciona tus archivos Excel 'Ventas_*.xlsx'", 
    type=['xlsx'], 
    accept_multiple_files=True
)

@st.cache_data
def procesar_archivos(lista_archivos):
    columnas = ['Fecha', 'Hora', 'Descripcion', 'Cantidad', 'Valor', 'Nombre Cajero', 'MOP1']
    lista_df = []
    for arc in lista_archivos:
        try:
            # Leer el archivo directamente de la memoria (subida web)
            df = pd.read_excel(arc, skiprows=7)
            # Seleccionar solo las columnas necesarias
            df_sel = df[columnas].copy()
            # Convertir fecha y limpiar filas vacías
            df_sel['Fecha'] = pd.to_datetime(df_sel['Fecha'], dayfirst=True, errors='coerce')
            df_sel = df_sel.dropna(subset=['Fecha'])
            lista_df.append(df_sel)
        except Exception as e:
            st.warning(f"No se pudo procesar un archivo: {arc.name}")
            continue
    
    if lista_df:
        return pd.concat(lista_df, ignore_index=True)
    return None

# Ejecutar la carga solo si hay archivos
df_base = None
if archivos_subidos:
    df_base = procesar_archivos(archivos_subidos)

# =========================================================
# 4. CUERPO PRINCIPAL Y FILTROS
# =========================================================
if df_base is not None:
    # --- PANEL DE FILTROS ---
    with st.expander("🔍 Panel de Filtros Avanzados", expanded=True):
        f1, f2, f3, f4 = st.columns(4)
        
        with f1:
            min_f, max_f = df_base['Fecha'].min(), df_base['Fecha'].max()
            rango = st.date_input("Periodo:", [min_f, max_f])
            
        with f2:
            vendedores = st.multiselect("Vendedor:", df_base['Nombre Cajero'].unique(), 
                                        default=df_base['Nombre Cajero'].unique())
            
        with f3:
            productos_sel = st.multiselect("Producto:", df_base['Descripcion'].unique(), 
                                          default=df_base['Descripcion'].unique())
            
        with f4:
            medios = st.multiselect("Pago:", df_base['MOP1'].unique(), 
                                   default=df_base['MOP1'].unique())

    # Aplicar Filtros
    mask = (df_base['Nombre Cajero'].isin(vendedores)) & \
           (df_base['MOP1'].isin(medios)) & \
           (df_base['Descripcion'].isin(productos_sel))
    
    if len(rango) == 2:
        mask &= (df_base['Fecha'] >= pd.Timestamp(rango[0])) & (df_base['Fecha'] <= pd.Timestamp(rango[1]))
    
    df_filtrado = df_base.loc[mask].copy()

    # Cálculo de Comisión
    df_filtrado['Pago_Comision'] = df_filtrado.apply(
        lambda x: x['Cantidad'] * TABLA_COMISIONES.get(str(x['Descripcion']).upper(), 0), axis=1
    )

    # --- MÉTRICAS PRINCIPALES ---
    st.divider()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Recaudación Total", f"$ {df_filtrado['Valor'].sum():,.0f}")
    m2.metric("Comisiones a Pagar", f"$ {df_filtrado['Pago_Comision'].sum():,.0f}")
    m3.metric("Litros/Unidades", f"{df_filtrado['Cantidad'].sum():,.1f}")
    m4.metric("N° de Ventas", len(df_filtrado))

    # --- GRÁFICOS Y TABLAS ---
    col_izq, col_der = st.columns([1, 1])

    with col_izq:
        st.subheader("💰 Resumen de Liquidación")
        resumen = df_filtrado.groupby('Nombre Cajero')['Pago_Comision'].sum().reset_index()
        resumen.columns = ['Cajero', 'Total Comisiones']
        st.dataframe(resumen.style.format({'Total Comisiones': '$ {:,.0f}'}), 
                     use_container_width=True)

    with col_der:
        st.subheader("📈 Flujo de Ventas por Hora")
        df_filtrado['Hora_H'] = df_filtrado['Hora'].astype(str).str[:2]
        ventas_hora = df_filtrado.groupby('Hora_H').size().reset_index(name='Tickets')
        fig_h = px.bar(ventas_hora, x='Hora_H', y='Tickets', 
                       color_discrete_sequence=['#004b87'])
        st.plotly_chart(fig_h, use_container_width=True)

    with st.expander("📋 Ver detalle de todas las transacciones"):
        st.write(df_filtrado)

else:
    st.info("👋 Por favor, selecciona tus archivos Excel 'Ventas_*.xlsx' en el cuadro de arriba para comenzar el análisis.")
