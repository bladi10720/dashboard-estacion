import streamlit as st
import pandas as pd
import plotly.express as px
import io

# =========================================================
# 1. CONFIGURACIÓN DE COMISIONES (CÓDIGOS O NOMBRES)
# =========================================================
# Ahora puedes mezclar: poner el código numérico o el nombre en mayúsculas
TABLA_COMISIONES = {
    '101': 5.0,         # Ejemplo: Código para Gasolina 93
    '102': 8.0,         # Ejemplo: Código para Gasolina 95
    '1050': 15.0,       # Código del Limpiaparabrisas
    'GASOLINA 97': 10.0,
    'DIESEL': 4.0,
    'KEROSENE': 6.0,
    'ACEITE MOTOR': 500.0,
    'ADBLUE': 16.0,
    'DIXSEL': 100.0
}

# =========================================================
# 2. CONFIGURACIÓN DE LA PÁGINA
# =========================================================
st.set_page_config(page_title="Estación Pro - Reportes", layout="wide", page_icon="⛽")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    [data-testid="stMetricValue"] { font-size: 28px; color: #004b87; }
    </style>
    """, unsafe_allow_html=True)

st.title("⛽ Sistema de Gestión de Ventas - Estación Pro")

# =========================================================
# 3. CARGA DE DATOS
# =========================================================
archivos_subidos = st.file_uploader(
    "📂 Selecciona tus archivos Excel 'Ventas_*.xlsx'", 
    type=['xlsx'], 
    accept_multiple_files=True
)

@st.cache_data
def procesar_archivos(lista_archivos):
    # Agregamos 'cod Producto' a la lista de columnas a extraer
    columnas_posibles = ['Fecha', 'Hora', 'cod Producto', 'Descripcion', 'Cantidad', 'Valor', 'Nombre Cajero', 'MOP1']
    lista_df = []
    
    for arc in lista_archivos:
        try:
            df = pd.read_excel(arc, skiprows=7)
            # Limpiar nombres de columnas por si traen espacios
            df.columns = [str(c).strip() for c in df.columns]
            
            # Verificar qué columnas de las que queremos existen realmente en este Excel
            cols_presentes = [c for c in columnas_posibles if c in df.columns]
            df_sel = df[cols_presentes].copy()
            
            # Convertir fecha y limpiar
            df_sel['Fecha'] = pd.to_datetime(df_sel['Fecha'], dayfirst=True, errors='coerce')
            df_sel = df_sel.dropna(subset=['Fecha'])
            lista_df.append(df_sel)
        except Exception as e:
            st.warning(f"No se pudo procesar el archivo {arc.name}: {e}")
            continue
    
    if lista_df:
        return pd.concat(lista_df, ignore_index=True)
    return None

df_base = None
if archivos_subidos:
    df_base = procesar_archivos(archivos_subidos)

# =========================================================
# 4. CUERPO PRINCIPAL Y FILTROS
# =========================================================
if df_base is not None:
    # --- PROCESAMIENTO DE IDENTIDAD (CÓDIGO + NOMBRE) ---
    if 'cod Producto' in df_base.columns:
        df_base['cod Producto'] = df_base['cod Producto'].astype(str).str.strip()
    
    df_base['Descripcion'] = df_base['Descripcion'].astype(str).str.strip()
    
    # Creamos la info combinada para los filtros y tablas
    if 'cod Producto' in df_base.columns:
        df_base['Producto_Info'] = df_base['cod Producto'] + " - " + df_base['Descripcion']
    else:
        df_base['Producto_Info'] = df_base['Descripcion']

    # --- PANEL DE FILTROS ---
    with st.expander("🔍 Panel de Filtros Avanzados", expanded=True):
        f1, f2, f3, f4 = st.columns(4)
        
        with f1:
            rango = st.date_input("Periodo:", [df_base['Fecha'].min(), df_base['Fecha'].max()])
            
        with f2:
            vendedores = st.multiselect("Vendedor:", df_base['Nombre Cajero'].unique(), 
                                        default=df_base['Nombre Cajero'].unique())
            
        with f3:
            productos_sel = st.multiselect("Producto (Cód - Desc):", df_base['Producto_Info'].unique(), 
                                          default=df_base['Producto_Info'].unique())
            
        with f4:
            medios = st.multiselect("Pago:", df_base['MOP1'].unique(), 
                                   default=df_base['MOP1'].unique())

    # Aplicar Filtros
    mask = (df_base['Nombre Cajero'].isin(vendedores)) & \
           (df_base['MOP1'].isin(medios)) & \
           (df_base['Producto_Info'].isin(productos_sel))
    
    if len(rango) == 2:
        mask &= (df_base['Fecha'] >= pd.Timestamp(rango[0])) & (df_base['Fecha'] <= pd.Timestamp(rango[1]))
    
    df_filtrado = df_base.loc[mask].copy()

    # --- CÁLCULO DE COMISIÓN INTELIGENTE ---
    def calcular_comision(fila):
        # 1. Intentar por código primero (si existe)
        if 'cod Producto' in fila and fila['cod Producto'] in TABLA_COMISIONES:
            return fila['Cantidad'] * TABLA_COMISIONES[fila['cod Producto']]
        # 2. Si no, intentar por nombre en mayúsculas
        nombre = str(fila['Descripcion']).upper()
        return fila['Cantidad'] * TABLA_COMISIONES.get(nombre, 0)

    df_filtrado['Pago_Comision'] = df_filtrado.apply(calcular_comision, axis=1)

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
        # Mostramos la columna combinada para que veas códigos y nombres juntos
        st.write(df_filtrado[['Fecha', 'Hora', 'Nombre Cajero', 'Producto_Info', 'Cantidad', 'Valor', 'Pago_Comision']])

else:
    st.info("👋 Por favor, selecciona tus archivos Excel 'Ventas_*.xlsx' para comenzar.")