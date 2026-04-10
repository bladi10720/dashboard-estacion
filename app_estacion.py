import streamlit as st
import pandas as pd
import plotly.express as px
import io
import re
from datetime import datetime

# =========================================================
# 1. CONFIGURACIÓN DE COMISIONES MEJORADA
# =========================================================
TABLA_COMISIONES = {
    # Códigos (como strings)
    '966879': 1000.0,    # Gasolina 93
    '102': 8.0,          # Gasolina 95
    '1050': 15.0,        # Limpiaparabrisas
    
    # Nombres (normalizados)
    'GASOLINA 97': 10.0,
    'DIESEL': 4.0,
    'KEROSENE': 6.0,
    'ACEITE MOTOR': 500.0,
    'ADBLUE': 16.0,
    'DIXSEL': 100.0,
    'PETROLEO DIESEL G-B': 100.0,
    'GASOLINA 93': 1000.0,
    'GASOLINA 95': 8.0,
    'bidon 20 lt comb gas': 5000
}

# =========================================================
# 2. FUNCIONES AUXILIARES
# =========================================================
def normalizar_texto(texto):
    """Normaliza texto para búsqueda (mayúsculas, sin espacios extra)"""
    if pd.isna(texto) or texto is None:
        return ''
    return str(texto).upper().strip()

def calcular_comision_segura(fila, tabla_comisiones):
    """
    Versión mejorada con manejo de errores y logging
    """
    try:
        cantidad = fila.get('Cantidad', 0)
        if pd.isna(cantidad) or cantidad <= 0:
            return 0.0
        
        # 1. Intentar por código (prioridad)
        codigo = normalizar_texto(fila.get('cod Producto', ''))
        if codigo and codigo in tabla_comisiones:
            return float(cantidad) * tabla_comisiones[codigo]
        
        # 2. Intentar por nombre (sin código)
        nombre = normalizar_texto(fila.get('Descripcion', ''))
        
        # Búsqueda exacta
        if nombre in tabla_comisiones:
            return float(cantidad) * tabla_comisiones[nombre]
        
        # 3. Búsqueda parcial (opcional - para nombres similares)
        for key, valor in tabla_comisiones.items():
            if key in nombre or nombre in key:
                return float(cantidad) * valor
        
        return 0.0
        
    except Exception as e:
        st.warning(f"Error calculando comisión para fila: {e}")
        return 0.0

def validar_datos(df):
    """Valida la calidad de los datos cargados"""
    if df is None or df.empty:
        return False, "No hay datos para procesar"
    
    problemas = []
    
    # Verificar columnas críticas
    columnas_requeridas = ['Fecha', 'Cantidad', 'Valor']
    for col in columnas_requeridas:
        if col not in df.columns:
            problemas.append(f"Falta columna: {col}")
    
    # Verificar valores nulos
    for col in ['Nombre Cajero', 'Descripcion']:
        if col in df.columns and df[col].isna().all():
            problemas.append(f"Todos los valores de '{col}' son nulos")
    
    # Verificar fechas inválidas
    if 'Fecha' in df.columns:
        fechas_invalidas = df['Fecha'].isna().sum()
        if fechas_invalidas > 0:
            problemas.append(f"{fechas_invalidas} fechas inválidas encontradas")
    
    if problemas:
        return False, "; ".join(problemas)
    
    return True, "Datos válidos"

def mostrar_metricas(df):
    """Muestra métricas con formato profesional"""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "💰 Recaudación Total", 
            f"${df['Valor'].sum():,.0f}",
            help="Suma total de todas las ventas"
        )
    
    with col2:
        comision_total = df['Pago_Comision'].sum()
        st.metric(
            "💵 Comisiones a Pagar", 
            f"${comision_total:,.0f}",
            help="Total a pagar en comisiones"
        )
    
    with col3:
        st.metric(
            "⛽ Litros/Unidades", 
            f"{df['Cantidad'].sum():,.1f}",
            help="Volumen total vendido"
        )
    
    with col4:
        st.metric(
            "📊 N° de Ventas", 
            f"{len(df):,}",
            help="Número total de transacciones"
        )

def crear_graficos(df_filtrado):
    """Crea gráficos interactivos adicionales"""
    tab1, tab2, tab3 = st.tabs(["📊 Por Hora", "📈 Tendencia", "🥧 Por Producto"])
    
    with tab1:
        if 'Hora' in df_filtrado.columns:
            df_filtrado['Hora_H'] = df_filtrado['Hora'].astype(str).str[:2]
            ventas_hora = df_filtrado.groupby('Hora_H').agg({
                'Valor': 'sum',
                'Cantidad': 'sum'
            }).reset_index()
            
            fig_h = px.bar(ventas_hora, x='Hora_H', y='Valor', 
                          title="Ventas por Hora",
                          color_discrete_sequence=['#004b87'],
                          labels={'Valor': 'Monto Vendido', 'Hora_H': 'Hora'})
            st.plotly_chart(fig_h, use_container_width=True)
    
    with tab2:
        if len(df_filtrado) > 1:
            ventas_dia = df_filtrado.groupby('Fecha').agg({
                'Valor': 'sum',
                'Cantidad': 'sum'
            }).reset_index()
            
            fig_line = px.line(ventas_dia, x='Fecha', y='Valor',
                              title="Evolución de Ventas",
                              markers=True)
            st.plotly_chart(fig_line, use_container_width=True)
    
    with tab3:
        top_productos = df_filtrado.groupby('Descripcion')['Valor'].sum().nlargest(10)
        if len(top_productos) > 0:
            fig_pie = px.pie(values=top_productos.values, 
                            names=top_productos.index,
                            title="Top 10 Productos por Ventas")
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No hay datos suficientes para mostrar el gráfico")

def exportar_reporte(df, nombre_archivo="reporte_comisiones.xlsx"):
    """Exporta el reporte a Excel con múltiples hojas"""
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Hoja 1: Detalle
        df_detalle = df[['Fecha', 'Hora', 'Nombre Cajero', 'Descripcion', 'Cantidad', 'Valor', 'Pago_Comision']].copy()
        df_detalle.to_excel(writer, sheet_name='Detalle Ventas', index=False)
        
        # Hoja 2: Resumen por Cajero
        resumen_cajero = df.groupby('Nombre Cajero').agg({
            'Valor': 'sum',
            'Pago_Comision': 'sum',
            'Cantidad': 'sum'
        }).round(2)
        resumen_cajero.columns = ['Total Ventas', 'Total Comisiones', 'Volumen']
        resumen_cajero['% Comisión'] = (resumen_cajero['Total Comisiones'] / resumen_cajero['Total Ventas'] * 100).round(2)
        resumen_cajero.to_excel(writer, sheet_name='Resumen por Cajero')
        
        # Hoja 3: Resumen por Producto
        resumen_producto = df.groupby('Descripcion').agg({
            'Valor': 'sum',
            'Cantidad': 'sum'
        }).nlargest(20, 'Valor')
        resumen_producto.columns = ['Total Ventas', 'Volumen']
        resumen_producto.to_excel(writer, sheet_name='Top Productos')
    
    return output.getvalue()

# =========================================================
# 3. CARGA DE DATOS MEJORADA
# =========================================================
@st.cache_data
def procesar_archivos(lista_archivos):
    columnas_posibles = ['Fecha', 'Hora', 'cod Producto', 'Descripcion', 
                        'Cantidad', 'Valor', 'Nombre Cajero', 'MOP1']
    lista_df = []
    errores = []
    
    for arc in lista_archivos:
        try:
            # Intentar detectar automáticamente dónde empiezan los datos
            df_temp = pd.read_excel(arc, header=None)
            
            # Buscar la fila que contiene 'Fecha' (encabezados)
            header_row = None
            for idx, row in df_temp.iterrows():
                if 'Fecha' in str(row.values):
                    header_row = idx
                    break
            
            if header_row is not None:
                df = pd.read_excel(arc, skiprows=header_row)
            else:
                df = pd.read_excel(arc, skiprows=7)  # Fallback original
            
            # Limpiar nombres de columnas
            df.columns = [str(c).strip().replace('\n', ' ') for c in df.columns]
            
            # Filtrar columnas que existen
            cols_presentes = [c for c in columnas_posibles if c in df.columns]
            
            if not cols_presentes:
                errores.append(f"{arc.name}: No se encontraron columnas esperadas")
                continue
                
            df_sel = df[cols_presentes].copy()
            
            # Conversión segura de fechas
            if 'Fecha' in df_sel.columns:
                df_sel['Fecha'] = pd.to_datetime(df_sel['Fecha'], 
                                                dayfirst=True, 
                                                errors='coerce')
                df_sel = df_sel.dropna(subset=['Fecha'])
            
            # Limpiar datos numéricos
            for col in ['Cantidad', 'Valor']:
                if col in df_sel.columns:
                    df_sel[col] = pd.to_numeric(df_sel[col], errors='coerce').fillna(0)
            
            # Limpiar datos de texto
            for col in ['Nombre Cajero', 'Descripcion']:
                if col in df_sel.columns:
                    df_sel[col] = df_sel[col].astype(str).fillna('').str.strip()
            
            lista_df.append(df_sel)
            
        except Exception as e:
            errores.append(f"{arc.name}: {str(e)}")
            continue
    
    # Mostrar errores si los hay
    if errores:
        for error in errores[:5]:  # Mostrar máximo 5 errores
            st.warning(f"⚠️ {error}")
    
    if lista_df:
        df_final = pd.concat(lista_df, ignore_index=True)
        return df_final, errores
    
    return None, errores

# =========================================================
# 4. CONFIGURACIÓN DE LA PÁGINA
# =========================================================
st.set_page_config(page_title="Estación Pro - Reportes", layout="wide", page_icon="⛽")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    [data-testid="stMetricValue"] { font-size: 28px; color: #004b87; }
    .stButton button { background-color: #004b87; color: white; }
    </style>
    """, unsafe_allow_html=True)

st.title("⛽ Sistema de Gestión de Ventas - Estación Pro")
st.markdown("---")

# =========================================================
# 5. CUERPO PRINCIPAL
# =========================================================
archivos_subidos = st.file_uploader(
    "📂 Selecciona tus archivos Excel 'Ventas_*.xlsx'", 
    type=['xlsx'], 
    accept_multiple_files=True,
    help="Puedes seleccionar uno o varios archivos Excel para procesar"
)

if archivos_subidos:
    with st.spinner('🔄 Procesando archivos...'):
        df_base, errores = procesar_archivos(archivos_subidos)
    
    if df_base is not None and not df_base.empty:
        # Validar datos
        es_valido, mensaje = validar_datos(df_base)
        
        if not es_valido:
            st.warning(f"⚠️ Advertencia: {mensaje}")
        else:
            st.success("✅ Datos cargados correctamente")
        
        # Mostrar estadísticas básicas
        with st.expander("📊 Estadísticas de Carga"):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Archivos", len(archivos_subidos))
            with col2:
                st.metric("Total Registros", len(df_base))
            with col3:
                st.metric("Rango de Fechas", 
                         f"{df_base['Fecha'].min().strftime('%d/%m/%Y')} - {df_base['Fecha'].max().strftime('%d/%m/%Y')}")
        
        # Procesar datos
        if 'cod Producto' in df_base.columns:
            df_base['cod Producto'] = df_base['cod Producto'].astype(str).str.strip()
        
        df_base['Descripcion'] = df_base['Descripcion'].astype(str).str.strip()
        
        if 'cod Producto' in df_base.columns:
            df_base['Producto_Info'] = df_base['cod Producto'] + " - " + df_base['Descripcion']
        else:
            df_base['Producto_Info'] = df_base['Descripcion']
        
        # Panel de filtros
        with st.expander("🔍 Panel de Filtros Avanzados", expanded=True):
            f1, f2, f3, f4 = st.columns(4)
            
            with f1:
                fecha_min = df_base['Fecha'].min()
                fecha_max = df_base['Fecha'].max()
                rango = st.date_input(
                    "📅 Periodo:", 
                    [fecha_min, fecha_max],
                    min_value=fecha_min,
                    max_value=fecha_max
                )
            
            with f2:
                vendedores_opciones = sorted(df_base['Nombre Cajero'].unique())
                vendedores = st.multiselect(
                    "👤 Vendedor:", 
                    vendedores_opciones,
                    default=vendedores_opciones,
                    help="Selecciona uno o más vendedores"
                )
            
            with f3:
                productos_opciones = sorted(df_base['Producto_Info'].unique())
                productos_sel = st.multiselect(
                    "🛒 Producto:", 
                    productos_opciones,
                    default=productos_opciones,
                    help="Selecciona uno o más productos"
                )
            
            with f4:
                if 'MOP1' in df_base.columns:
                    medios_opciones = sorted(df_base['MOP1'].dropna().unique())
                    if medios_opciones:
                        medios = st.multiselect(
                            "💳 Método de Pago:", 
                            medios_opciones,
                            default=medios_opciones,
                            help="Selecciona uno o más métodos de pago"
                        )
                    else:
                        medios = []
                        st.info("No hay datos de método de pago")
                else:
                    medios = []
                    st.info("No hay datos de método de pago")
        
        # Aplicar filtros
        mask = pd.Series([True] * len(df_base))
        
        if vendedores:
            mask &= df_base['Nombre Cajero'].isin(vendedores)
        if medios:
            mask &= df_base['MOP1'].isin(medios)
        if productos_sel:
            mask &= df_base['Producto_Info'].isin(productos_sel)
        if len(rango) == 2:
            mask &= (df_base['Fecha'] >= pd.Timestamp(rango[0])) & \
                    (df_base['Fecha'] <= pd.Timestamp(rango[1]))
        
        df_filtrado = df_base.loc[mask].copy()
        
        if df_filtrado.empty:
            st.warning("⚠️ No hay datos que coincidan con los filtros seleccionados")
        else:
            # Calcular comisiones con función mejorada
            with st.spinner('💰 Calculando comisiones...'):
                df_filtrado['Pago_Comision'] = df_filtrado.apply(
                    lambda row: calcular_comision_segura(row, TABLA_COMISIONES), 
                    axis=1
                )
            
            st.success(f"✅ Mostrando {len(df_filtrado):,} registros")
            st.markdown("---")
            
            # Mostrar métricas
            mostrar_metricas(df_filtrado)
            
            st.markdown("---")
            
            # Mostrar gráficos
            crear_graficos(df_filtrado)
            
            # Tabla de resumen por cajero
            with st.expander("💰 Resumen de Liquidación por Cajero", expanded=True):
                resumen = df_filtrado.groupby('Nombre Cajero').agg({
                    'Pago_Comision': 'sum',
                    'Valor': 'sum',
                    'Cantidad': 'sum'
                }).round(2)
                resumen.columns = ['Total Comisiones', 'Total Ventas', 'Volumen']
                resumen['% Comisión'] = (resumen['Total Comisiones'] / resumen['Total Ventas'] * 100).round(2)
                resumen = resumen.sort_values('Total Comisiones', ascending=False)
                
                st.dataframe(resumen.style.format({
                    'Total Comisiones': '${:,.0f}',
                    'Total Ventas': '${:,.0f}',
                    'Volumen': '{:,.1f}',
                    '% Comisión': '{:.2f}%'
                }), use_container_width=True)
            
            # Detalle de transacciones
            with st.expander("📋 Ver detalle de todas las transacciones"):
                columnas_mostrar = ['Fecha', 'Hora', 'Nombre Cajero', 'Producto_Info', 'Cantidad', 'Valor', 'Pago_Comision']
                columnas_disponibles = [col for col in columnas_mostrar if col in df_filtrado.columns]
                
                st.dataframe(
                    df_filtrado[columnas_disponibles].style.format({
                        'Valor': '${:,.0f}',
                        'Pago_Comision': '${:,.0f}',
                        'Cantidad': '{:,.1f}'
                    }),
                    use_container_width=True,
                    height=400
                )
            
            # Exportar reporte
            st.markdown("---")
            col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
            with col_btn2:
                if st.button("📥 Exportar Reporte a Excel", use_container_width=True):
                    with st.spinner('Generando reporte...'):
                        excel_data = exportar_reporte(df_filtrado)
                        st.download_button(
                            label="💾 Descargar Reporte",
                            data=excel_data,
                            file_name=f"reporte_comisiones_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
    
    else:
        st.error("❌ No se pudieron procesar los archivos. Verifica el formato de los archivos Excel.")
        
        # Mostrar ayuda
        with st.expander("🆘 ¿Necesitas ayuda?"):
            st.markdown("""
            **Formato esperado del archivo Excel:**
            - El archivo debe tener las siguientes columnas:
                - `Fecha` (formato dd/mm/yyyy)
                - `Hora` (formato HH:MM:SS)
                - `Descripcion` (nombre del producto)
                - `Cantidad` (número de unidades/litros)
                - `Valor` (monto de la venta)
                - `Nombre Cajero` (nombre del vendedor)
            - Opcionalmente puede incluir:
                - `cod Producto` (código del producto)
                - `MOP1` (método de pago)
            
            **Consejos:**
            1. Asegúrate de que los archivos no estén corruptos
            2. Verifica que las columnas tengan los nombres exactos
            3. Prueba con un solo archivo primero
            """)

else:
    st.info("👋 **Bienvenido al Sistema de Gestión de Ventas**\n\nPor favor, selecciona tus archivos Excel 'Ventas_*.xlsx' para comenzar a analizar tus datos.")
    
    # Mostrar ejemplo
    with st.expander("📖 Ver ejemplo de uso"):
        st.markdown("""
        ### ¿Cómo usar esta aplicación?
        
        1. **Prepara tus archivos Excel** con el formato de ventas de tu estación
        2. **Carga uno o varios archivos** usando el botón de arriba
        3. **Aplica filtros** para analizar periodos específicos, vendedores o productos
        4. **Visualiza métricas** y gráficos automáticos
        5. **Exporta reportes** a Excel con un solo clic
        
        ### Características:
        - ✅ Soporte para múltiples archivos
        - ✅ Cálculo automático de comisiones
        - ✅ Filtros dinámicos
        - ✅ Gráficos interactivos
        - ✅ Exportación a Excel
        - ✅ Manejo robusto de errores
        """)

# =========================================================
# 6. FOOTER
# =========================================================
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray; font-size: 12px;'>"
    "© 2024 Estación Pro - Sistema de Gestión de Ventas | "
    "Desarrollado con Streamlit"
    "</div>",
    unsafe_allow_html=True
)