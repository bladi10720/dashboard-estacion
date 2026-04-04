import streamlit as st
import pandas as pd
import glob
import os
import plotly.express as px

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
    'ADBLUE':16
}

# =========================================================
# 2. CONFIGURACIÓN DE LA PÁGINA
# =========================================================
st.set_page_config(page_title="Estación Pro - Reportes", layout="wide", page_icon="⛽")

# Estilo CSS para que las métricas y contenedores resalten
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    [data-testid="stMetricValue"] { font-size: 28px; color: #004b87; }
    .stSelectbox, .stMultiSelect { background-color: #ffffff; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# =========================================================
# 3. CARGA DE DATOS (Mantenemos tu lógica robusta)
# =========================================================
@st.cache_data
def cargar_datos_maestros():
    ruta_carpeta = os.path.dirname(__file__)
    patron = os.path.join(ruta_carpeta, "Ventas_*.xlsx")
    archivos = glob.glob(patron)
    columnas = ['Fecha', 'Hora', 'Descripcion', 'Cantidad', 'Valor', 'Nombre Cajero', 'MOP1']
    lista = []
    for arc in archivos:
        try:
            df = pd.read_excel(arc, skiprows=7)
            df_sel = df[columnas].copy()
            df_sel['Fecha'] = pd.to_datetime(df_sel['Fecha'], dayfirst=True, errors='coerce')
            df_sel = df_sel.dropna(subset=['Fecha'])
            lista.append(df_sel)
        except: continue
    return pd.concat(lista, ignore_index=True) if lista else None

df_base = cargar_datos_maestros()

# =========================================================
# 4. CUERPO PRINCIPAL Y FILTROS ORGANIZADOS
# =========================================================
if df_base is not None:
    st.title("⛽ Sistema de Gestión de Ventas")
    
    # --- FILTROS EN COLUMNAS (Estilo Header) ---
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
        lambda x: x['Cantidad'] * TABLA_COMISIONES.get(x['Descripcion'], 0), axis=1
    )

    # --- MÉTRICAS PRINCIPALES ---
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Recaudación", f"$ {df_filtrado['Valor'].sum():,.0f}")
    m2.metric("Comisiones", f"$ {df_filtrado['Pago_Comision'].sum():,.0f}")
    m3.metric("Litros/Unid.", f"{df_filtrado['Cantidad'].sum():,.1f}")
    m4.metric("Ventas", len(df_filtrado))

    st.divider()

    # --- CONTENIDO ---
    col_izq, col_der = st.columns([1, 1]) # 50% y 50%

    with col_izq:
        st.subheader("💰 Resumen de Liquidación")
        resumen = df_filtrado.groupby('Nombre Cajero')['Pago_Comision'].sum().reset_index()
        resumen.columns = ['Cajero', 'Total Comisiones']
        st.dataframe(resumen.style.format({'Total Comisiones': '$ {:,.0f}'})
                     .highlight_max(subset=['Total Comisiones'], color='#e1f5fe'), 
                     use_container_width=True)

    with col_der:
        # Gráfico de Horas Pico (Más limpio)
        df_filtrado['Hora_H'] = df_filtrado['Hora'].astype(str).str[:2]
        ventas_hora = df_filtrado.groupby('Hora_H').size().reset_index(name='Tickets')
        fig_h = px.area(ventas_hora, x='Hora_H', y='Tickets', title="Flujo de Clientes",
                        color_discrete_sequence=['#004b87'])
        st.plotly_chart(fig_h, use_container_width=True)

    # Tabla de detalle al final
    with st.expander("📋 Ver detalle de todas las transacciones filtradas"):
        st.write(df_filtrado)

else:
    st.info("👋 Sube tus archivos Excel 'Ventas_*.xlsx' para comenzar.")