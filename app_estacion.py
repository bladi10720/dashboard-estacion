import streamlit as st
import pandas as pd
import plotly.express as px
import io
import re
import json
import os
import glob
from datetime import datetime
from difflib import get_close_matches
# CONVERTIR VALORES
def convertir_a_string(valores):
    """Convierte cualquier valor a string de forma segura"""
    return sorted([str(v) for v in valores if pd.notna(v)])

# =========================================================
# ACTUALIZACIÓN: 11 de abril de 2026 - Corrección de gráficos
# =========================================================

# =========================================================
# CONFIGURACIÓN DE LA PÁGINA
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
# CONFIGURACIÓN DE COMISIONES (Persistente)
# =========================================================

ARCHIVO_COMISIONES = "comisiones_guardadas.json"

# =========================================================
# FUNCIONES DE UTILIDAD
# =========================================================

def normalizar_texto(texto):
    """Normaliza texto para búsqueda"""
    if pd.isna(texto) or texto is None:
        return ''
    texto = str(texto).upper().strip()
    texto = re.sub(r'\s+', ' ', texto)
    texto = re.sub(r'[°\-_/\\|]', ' ', texto)
    return texto.strip()

def buscar_comision_por_similitud(nombre_producto, tabla_comisiones, umbral=0.8):
    """Busca comisión usando similitud de texto (fuzzy matching)"""
    if not nombre_producto:
        return None
    
    nombres_disponibles = list(tabla_comisiones.keys())
    matches = get_close_matches(nombre_producto, nombres_disponibles, n=1, cutoff=umbral)
    
    if matches:
        return tabla_comisiones[matches[0]]
    return None

def buscar_comision_por_palabras_clave(nombre_producto, palabras_clave):
    """Busca comisión usando palabras clave"""
    if not nombre_producto:
        return None
    
    for palabra, comision in palabras_clave.items():
        if palabra in nombre_producto:
            return comision
    return None

def calcular_comision_segura(fila, tabla_comisiones, palabras_clave):
    """Calcula comisión con múltiples estrategias de búsqueda"""
    try:
        cantidad = fila.get('Cantidad', 0)
        if pd.isna(cantidad) or cantidad <= 0:
            return 0.0
        
        codigo = normalizar_texto(fila.get('cod Producto', ''))
        nombre = normalizar_texto(fila.get('Descripcion', ''))
        
        # Estrategia 1: Por código
        if codigo and codigo in tabla_comisiones:
            return float(cantidad) * tabla_comisiones[codigo]
        
        # Estrategia 2: Por nombre exacto
        if nombre and nombre in tabla_comisiones:
            return float(cantidad) * tabla_comisiones[nombre]
        
        # Estrategia 3: Por similitud
        if nombre:
            comision_simil = buscar_comision_por_similitud(nombre, tabla_comisiones)
            if comision_simil:
                return float(cantidad) * comision_simil
        
        # Estrategia 4: Por palabras clave
        if nombre:
            comision_palabra = buscar_comision_por_palabras_clave(nombre, palabras_clave)
            if comision_palabra:
                return float(cantidad) * comision_palabra
        
        return 0.0
        
    except Exception as e:
        return 0.0

def mostrar_metricas(df):
    """Muestra métricas principales"""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("💰 Recaudación Total", f"${df['Valor'].sum():,.0f}")
    
    with col2:
        st.metric("💵 Comisiones a Pagar", f"${df['Pago_Comision'].sum():,.0f}")
    
    with col3:
        st.metric("⛽ Litros/Unidades", f"{df['Cantidad'].sum():,.1f}")
    
    with col4:
        st.metric("📊 N° de Ventas", f"{len(df):,}")

def crear_graficos(df):
    """Crea gráficos interactivos"""
    tab1, tab2, tab3 = st.tabs(["📊 Por Hora", "📈 Tendencia", "🥧 Por Producto"])
    
    with tab1:
        if 'Hora' in df.columns:
            df['Hora_H'] = df['Hora'].astype(str).str[:2]
            ventas_hora = df.groupby('Hora_H')['Valor'].sum().reset_index()
            fig = px.bar(ventas_hora, x='Hora_H', y='Valor', 
                        title="Ventas por Hora",
                        color_discrete_sequence=['#004b87'])
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay datos de hora para mostrar")
    
    with tab2:
        if len(df) > 1 and 'Fecha' in df.columns:
            ventas_dia = df.groupby('Fecha')['Valor'].sum().reset_index()
            fig = px.line(ventas_dia, x='Fecha', y='Valor',
                         title="Evolución de Ventas", markers=True)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay suficientes datos para la tendencia")
    
    with tab3:
        if 'Descripcion' in df.columns:
            top_productos = df.groupby('Descripcion')['Valor'].sum().nlargest(10)
            if len(top_productos) > 0:
                fig = px.pie(values=top_productos.values, 
                            names=top_productos.index,
                            title="Top 10 Productos por Ventas")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No hay datos de productos")

def exportar_reporte(df):
    """Exporta el reporte a Excel con múltiples hojas"""
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Hoja 1: Detalle
        df.to_excel(writer, sheet_name='Detalle Ventas', index=False)
        
        # Hoja 2: Resumen por Cajero
        if 'Nombre Cajero' in df.columns:
            resumen = df.groupby('Nombre Cajero').agg({
                'Valor': 'sum',
                'Pago_Comision': 'sum',
                'Cantidad': 'sum'
            }).round(2)
            resumen.columns = ['Total Ventas', 'Total Comisiones', 'Volumen']
            resumen.to_excel(writer, sheet_name='Resumen por Cajero')
        
        # Hoja 3: Resumen por Producto
        if 'Descripcion' in df.columns:
            top_productos = df.groupby('Descripcion').agg({
                'Valor': 'sum',
                'Cantidad': 'sum'
            }).nlargest(20, 'Valor')
            top_productos.columns = ['Total Ventas', 'Volumen']
            top_productos.to_excel(writer, sheet_name='Top Productos')
    
    return output.getvalue()

def procesar_archivos(lista_archivos):
    """Procesa archivos subidos manualmente"""
    columnas_posibles = ['Fecha', 'Hora', 'cod Producto', 'Descripcion', 
                        'Cantidad', 'Valor', 'Nombre Cajero', 'MOP1']
    lista_df = []
    errores = []
    
    for arc in lista_archivos:
        try:
            # Detectar encabezados automáticamente
            df_temp = pd.read_excel(arc, header=None)
            header_row = None
            for idx, row in df_temp.iterrows():
                if 'Fecha' in str(row.values):
                    header_row = idx
                    break
            
            if header_row is not None:
                df = pd.read_excel(arc, skiprows=header_row)
            else:
                df = pd.read_excel(arc, skiprows=7)
            
            df.columns = [str(c).strip().replace('\n', ' ') for c in df.columns]
            cols_presentes = [c for c in columnas_posibles if c in df.columns]
            
            if not cols_presentes:
                errores.append(f"{arc.name}: Columnas no encontradas")
                continue
            
            df_sel = df[cols_presentes].copy()
            
            if 'Fecha' in df_sel.columns:
                df_sel['Fecha'] = pd.to_datetime(df_sel['Fecha'], dayfirst=True, errors='coerce')
                df_sel = df_sel.dropna(subset=['Fecha'])
            
            for col in ['Cantidad', 'Valor']:
                if col in df_sel.columns:
                    df_sel[col] = pd.to_numeric(df_sel[col], errors='coerce').fillna(0)
            
            for col in ['Nombre Cajero', 'Descripcion']:
                if col in df_sel.columns:
                    df_sel[col] = df_sel[col].astype(str).fillna('').str.strip()
            
            lista_df.append(df_sel)
            
        except Exception as e:
            errores.append(f"{arc.name}: {str(e)}")
    
    if lista_df:
        return pd.concat(lista_df, ignore_index=True), errores
    return None, errores

def cargar_comisiones_desde_excel():
    """Carga las comisiones desde el archivo COMISION.xlsx"""
    
    # Verificar si la carpeta datos existe
    if not os.path.exists("datos"):
        st.error("❌ La carpeta 'datos/' no existe")
        return {}
    
    # Verificar si COMISION.xlsx está en la carpeta
    ruta = "datos/COMISION.xlsx"
    if not os.path.exists(ruta):
        st.error("❌ No se encontró el archivo COMISION.xlsx en la carpeta 'datos/'")
        return {}
    
    try:
        # Leer el archivo
        df = pd.read_excel(ruta)
        
        # La primera columna es códigos, la segunda es comisiones
        col_codigo = df.columns[0]
        col_comision = df.columns[1]
        
        comisiones = {}
        
        for _, row in df.iterrows():
            codigo = str(row[col_codigo]).strip()
            comision = row[col_comision]
            
            # Validar que no sea vacío
            if pd.notna(codigo) and pd.notna(comision) and codigo != 'nan' and comision != 0:
                try:
                    comisiones[codigo] = float(comision)
                except:
                    pass
        
        if comisiones:
            st.success(f"✅ Cargadas {len(comisiones)} comisiones desde Excel")
            return comisiones
        else:
            st.warning("⚠️ No se encontraron comisiones válidas en el archivo")
            return {}
            
    except Exception as e:
        st.error(f"❌ Error al leer el archivo: {e}")
        return {}

def cargar_comisiones():
    """Carga comisiones SOLO desde Excel"""
    
    comisiones = cargar_comisiones_desde_excel()
    
    if not comisiones:
        st.error("❌ No se pudieron cargar las comisiones. Verifica el archivo COMISION.xlsx")
    
    return comisiones

def guardar_comisiones(comisiones):
    """Guarda las comisiones en un archivo JSON"""
    try:
        with open(ARCHIVO_COMISIONES, 'w', encoding='utf-8') as f:
            json.dump(comisiones, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"Error al guardar comisiones: {e}")
        return False

def cargar_desde_github():
    """Carga archivos desde la carpeta 'datos/' de GitHub"""
    if not os.path.exists("datos"):
        return None
    
    archivos = glob.glob("datos/*.xlsx")
    if not archivos:
        return None
    
    lista_df = []
    for archivo in archivos:
        try:
            df = pd.read_excel(archivo, skiprows=7)
            df.columns = [str(c).strip() for c in df.columns]
            
            if 'Fecha' in df.columns:
                df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True, errors='coerce')
                df = df.dropna(subset=['Fecha'])
            
            for col in ['Cantidad', 'Valor']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            lista_df.append(df)
            
        except Exception as e:
            st.warning(f"Error en {os.path.basename(archivo)}: {e}")
    
    if lista_df:
        return pd.concat(lista_df, ignore_index=True)
    return None

def interfaz_gestion_comisiones():
    """Interfaz para gestionar comisiones"""
    with st.expander("⚙️ Gestión de Comisiones", expanded=False):
        st.subheader("➕ Agregar Nueva Comisión")
        
        col1, col2 = st.columns(2)
        
        with col1:
            nuevo_producto = st.text_input(
                "Nombre del producto:",
                placeholder="Ej: BIDON 20 LT COMB GAS"
            )
        
        with col2:
            nueva_comision = st.number_input(
                "Comisión por unidad ($):",
                min_value=0.0,
                step=100.0,
                format="%.2f"
            )
        
        if st.button("💾 Guardar Comisión", use_container_width=True):
            if nuevo_producto and nueva_comision > 0:
                nombre_normalizado = normalizar_texto(nuevo_producto)
                st.session_state.TABLA_COMISIONES[nombre_normalizado] = nueva_comision
                guardar_comisiones(st.session_state.TABLA_COMISIONES)
                st.success(f"✅ Comisión guardada: {nombre_normalizado} = ${nueva_comision:,.2f}")
                st.rerun()
            else:
                st.error("❌ Completa todos los campos")
        
        st.divider()
        
        st.subheader("🗑️ Eliminar Comisión")
        if len(st.session_state.TABLA_COMISIONES) > 0:
            comision_a_eliminar = st.selectbox(
                "Selecciona comisión para eliminar:",
                options=list(st.session_state.TABLA_COMISIONES.keys())
            )
            
            if st.button("❌ Eliminar Comisión", use_container_width=True):
                del st.session_state.TABLA_COMISIONES[comision_a_eliminar]
                guardar_comisiones(st.session_state.TABLA_COMISIONES)
                st.success(f"✅ Comisión eliminada: {comision_a_eliminar}")
                st.rerun()
        
        st.divider()
        
        st.subheader("📋 Comisiones Activas")
        if len(st.session_state.TABLA_COMISIONES) > 0:
            df_comisiones = pd.DataFrame([
                {'Producto/Código': k, 'Comisión por Unidad': f"${v:,.2f}"}
                for k, v in st.session_state.TABLA_COMISIONES.items()
            ])
            st.dataframe(df_comisiones, use_container_width=True, height=300)

# =========================================================
# INICIALIZAR ESTADO (después de todas las funciones)
# =========================================================

if 'TABLA_COMISIONES' not in st.session_state:
    st.session_state.TABLA_COMISIONES = cargar_comisiones()

if 'datos_github' not in st.session_state:
    st.session_state.datos_github = None

# Palabras clave para búsqueda flexible
PALABRAS_CLAVE_COMISIONES = {
    'BIDON': 5000.0,
    'BIDON 20': 5000.0,
    '20 LT': 5000.0,
    '20L': 5000.0,
    'COMB GAS': 5000.0,
}

# =========================================================
# INTERFAZ PRINCIPAL - CARGA DE DATOS
# =========================================================

with st.expander("📁 Fuente de Datos", expanded=True):
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📂 Datos desde GitHub")
        
        # Mostrar archivos disponibles
        if os.path.exists("datos"):
            archivos = glob.glob("datos/*.xlsx")
            if archivos:
                st.info(f"📄 {len(archivos)} archivo(s) en GitHub")
                for a in archivos[:5]:
                    st.caption(f"• {os.path.basename(a)}")
            else:
                st.warning("No hay archivos en la carpeta 'datos/'")
        
        if st.button("🔄 Cargar desde GitHub", use_container_width=True):
            with st.spinner('Cargando archivos...'):
                df_temp = cargar_desde_github()
                if df_temp is not None:
                    st.session_state.datos_github = df_temp
                    st.success(f"✅ Cargados {len(df_temp)} registros desde GitHub")
                    st.rerun()
                else:
                    st.error("No se encontraron archivos en la carpeta 'datos/'")
    
    with col2:
        st.markdown("### 💻 Carga Manual")
        archivos_subidos = st.file_uploader(
            "Selecciona tus archivos Excel", 
            type=['xlsx'], 
            accept_multiple_files=True,
            help="Puedes seleccionar uno o varios archivos"
        )

# =========================================================
# SELECCIONAR FUENTE DE DATOS
# =========================================================

df_base = None

if archivos_subidos:
    with st.spinner('Procesando archivos manuales...'):
        df_base, errores = procesar_archivos(archivos_subidos)
        if df_base is not None:
            st.session_state.datos_github = None
            st.success(f"✅ Cargados {len(df_base)} registros manualmente")
            if errores:
                for error in errores[:3]:
                    st.warning(f"⚠️ {error}")
elif st.session_state.datos_github is not None:
    df_base = st.session_state.datos_github
    st.info(f"📊 Usando datos de GitHub ({len(df_base)} registros)")

# =========================================================
# PROCESAR Y MOSTRAR DATOS
# =========================================================

if df_base is not None and not df_base.empty:
    # Limpiar y preparar datos
    if 'cod Producto' in df_base.columns:
        df_base['cod Producto'] = df_base['cod Producto'].astype(str).str.strip()
    df_base['Descripcion'] = df_base['Descripcion'].astype(str).str.strip()
    
    if 'cod Producto' in df_base.columns:
        df_base['Producto_Info'] = df_base['cod Producto'] + " - " + df_base['Descripcion']
    else:
        df_base['Producto_Info'] = df_base['Descripcion']
    
    # Gestión de comisiones
    interfaz_gestion_comisiones()
    
    # =========================================================
    # FILTROS DINÁMICOS
    # =========================================================
    with st.expander("🔍 Filtros Avanzados", expanded=True):
        f1, f2, f3, f4 = st.columns(4)
        
        with f1:
            if 'Fecha' in df_base.columns:
                fecha_min = df_base['Fecha'].min()
                fecha_max = df_base['Fecha'].max()
                rango = st.date_input(
                    "📅 Periodo:", 
                    [fecha_min, fecha_max],
                    min_value=fecha_min,
                    max_value=fecha_max
                )
            else:
                rango = []
        
        with f2:
            if 'Nombre Cajero' in df_base.columns:
                vendedores_opciones = convertir_a_string(df_base['Nombre Cajero'].unique())
                vendedores = st.multiselect(
                    "👤 Vendedor:", 
                    vendedores_opciones,
                    default=vendedores_opciones
                )
            else:
                vendedores = []
        
        with f3:
            if 'Producto_Info' in df_base.columns:
                productos_opciones = convertir_a_string(df_base['Producto_Info'].unique())
                productos = st.multiselect(
                    "🛒 Producto:", 
                    productos_opciones,
                    default=productos_opciones
                )
            else:
                productos = []
        
        with f4:
            if 'MOP1' in df_base.columns:
                medios_opciones = convertir_a_string(df_base['MOP1'].dropna().unique())
                if medios_opciones:
                    medios = st.multiselect(
                        "💳 Método de Pago:", 
                        medios_opciones,
                        default=medios_opciones
                    )
                else:
                    medios = []
            else:
                medios = []
    # =========================================================
    # APLICAR FILTROS
    # =========================================================
    mask = pd.Series([True] * len(df_base))
    
    if 'rango' in locals() and len(rango) == 2:
        mask &= (df_base['Fecha'] >= pd.Timestamp(rango[0])) & \
                (df_base['Fecha'] <= pd.Timestamp(rango[1]))
    
    if 'vendedores' in locals() and vendedores:
        mask &= df_base['Nombre Cajero'].isin(vendedores)
    
    if 'productos' in locals() and productos:
        mask &= df_base['Producto_Info'].isin(productos)
    
    if 'medios' in locals() and medios:
        mask &= df_base['MOP1'].isin(medios)
    
    df_filtrado = df_base.loc[mask].copy()
    
    # =========================================================
    # MOSTRAR RESULTADOS
    # =========================================================
    if df_filtrado.empty:
        st.warning("⚠️ No hay datos que coincidan con los filtros seleccionados")
        st.info("💡 Prueba a seleccionar menos filtros o ampliar el rango de fechas")
    else:
        # Calcular comisiones
        with st.spinner('💰 Calculando comisiones...'):
            df_filtrado['Pago_Comision'] = df_filtrado.apply(
                lambda row: calcular_comision_segura(
                    row, 
                    st.session_state.TABLA_COMISIONES, 
                    PALABRAS_CLAVE_COMISIONES
                ), 
                axis=1
            )
        
        st.success(f"✅ Mostrando {len(df_filtrado):,} registros")
        st.markdown("---")
        
        # Métricas principales
        mostrar_metricas(df_filtrado)
        st.markdown("---")
        
        # Gráficos
        crear_graficos(df_filtrado)
        
        # Resumen por vendedor
        with st.expander("💰 Resumen de Liquidación por Cajero", expanded=True):
            if 'Nombre Cajero' in df_filtrado.columns:
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
        
        # Resumen por producto
        with st.expander("📊 Comisiones por Producto"):
            if 'Descripcion' in df_filtrado.columns:
                resumen_prod = df_filtrado.groupby('Descripcion').agg({
                    'Cantidad': 'sum',
                    'Pago_Comision': 'sum',
                    'Valor': 'sum'
                }).round(2)
                resumen_prod = resumen_prod[resumen_prod['Pago_Comision'] > 0]
                resumen_prod = resumen_prod.sort_values('Pago_Comision', ascending=False)
                
                if not resumen_prod.empty:
                    st.dataframe(resumen_prod.style.format({
                        'Cantidad': '{:,.1f}',
                        'Pago_Comision': '${:,.0f}',
                        'Valor': '${:,.0f}'
                    }), use_container_width=True)
                else:
                    st.info("No hay comisiones calculadas para los productos filtrados")
        
        # Detalle de transacciones
        with st.expander("📋 Detalle de Transacciones"):
            columnas = ['Fecha', 'Hora', 'Nombre Cajero', 'Producto_Info', 'Cantidad', 'Valor', 'Pago_Comision']
            columnas_existentes = [c for c in columnas if c in df_filtrado.columns]
            st.dataframe(
                df_filtrado[columnas_existentes].style.format({
                    'Valor': '${:,.0f}',
                    'Pago_Comision': '${:,.0f}',
                    'Cantidad': '{:,.1f}'
                }),
                use_container_width=True,
                height=400
            )
        
        # Exportar
        st.markdown("---")
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

elif archivos_subidos is None and st.session_state.datos_github is None:
    st.info("👋 **Bienvenido al Sistema de Gestión de Ventas**\n\nSelecciona archivos Excel o usa 'Cargar desde GitHub' para comenzar")
    
    with st.expander("📖 Guía Rápida"):
        st.markdown("""
        ### Características de la aplicación:
        - ✅ Soporte para múltiples archivos
        - ✅ Cálculo automático de comisiones
        - ✅ Filtros dinámicos (fecha, vendedor, producto, método de pago)
        - ✅ Gráficos interactivos
        - ✅ Exportación a Excel
        - ✅ Manejo robusto de errores
        - ✅ Detección flexible de productos
        - ✅ Gestión de comisiones integrada
        """)

# =========================================================
# FOOTER
# =========================================================
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray; font-size: 12px;'>"
    "© 2024 Estación Pro - Sistema de Gestión de Ventas | "
    "Las comisiones se guardan automáticamente"
    "</div>",
    unsafe_allow_html=True
)        