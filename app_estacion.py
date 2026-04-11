import streamlit as st
import pandas as pd
import plotly.express as px
import io
import re
import json
import os
import glob          # ← Agrega ESTA línea
from datetime import datetime
from difflib import get_close_matches

# =========================================================
# 1. CONFIGURACIÓN DE COMISIONES CON PERSISTENCIA
# =========================================================

ARCHIVO_COMISIONES = "comisiones_guardadas.json"

def cargar_comisiones():
    """Carga las comisiones desde un archivo JSON"""
    comisiones_por_defecto = {
        '966879': 1000.0,
        '102': 8.0,
        '1050': 15.0,
        'GASOLINA 97': 10.0,
        'DIESEL': 4.0,
        'KEROSENE': 6.0,
        'ACEITE MOTOR': 500.0,
        'ADBLUE': 16.0,
        'DIXSEL': 100.0,
        'PETROLEO DIESEL G-B': 100.0,
        'GASOLINA 93': 1000.0,
        'GASOLINA 95': 8.0,
        'BIDON 20 LT COMB GAS': 5000.0,
        'BIDON 20L COMB GAS': 5000.0,
        'BIDON 20 LT': 5000.0,
        'BIDON 20L': 5000.0,
        'BIDON GASOLINA 20L': 5000.0,
        'BIDON 20 LITROS': 5000.0,
    }
    
    if os.path.exists(ARCHIVO_COMISIONES):
        try:
            with open(ARCHIVO_COMISIONES, 'r', encoding='utf-8') as f:
                comisiones_guardadas = json.load(f)
                comisiones_por_defecto.update(comisiones_guardadas)
        except:
            pass
    
    return comisiones_por_defecto

def guardar_comisiones(comisiones):
    """Guarda las comisiones en un archivo JSON"""
    try:
        with open(ARCHIVO_COMISIONES, 'w', encoding='utf-8') as f:
            json.dump(comisiones, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"Error al guardar comisiones: {e}")
        return False

# Cargar comisiones al iniciar
# Cargar comisiones al iniciar
if 'TABLA_COMISIONES' not in st.session_state:
    st.session_state.TABLA_COMISIONES = cargar_comisiones()

# Variables para controlar la carga automática (esto va FUERA del if anterior)
if 'datos_cargados' not in st.session_state:
    st.session_state.datos_cargados = None

if 'tipo_carga' not in st.session_state:
    st.session_state.tipo_carga = None
    st.session_state.TABLA_COMISIONES = cargar_comisiones()

# Palabras clave para búsqueda flexible
PALABRAS_CLAVE_COMISIONES = {
    'BIDON': 5000.0,
    'BIDON 20': 5000.0,
    '20 LT': 5000.0,
    '20L': 5000.0,
    'COMB GAS': 5000.0,
}

# =========================================================
# 2. FUNCIONES AUXILIARES
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
    """Busca comisión usando similitud de texto"""
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
    
    nombre_upper = nombre_producto.upper()
    for palabra, comision in palabras_clave.items():
        if palabra in nombre_upper:
            return comision
    return None

def calcular_comision_segura(fila, tabla_comisiones, palabras_clave):
    """
    Versión mejorada con múltiples estrategias de búsqueda
    """
    try:
        cantidad = fila.get('Cantidad', 0)
        if pd.isna(cantidad) or cantidad <= 0:
            return 0.0
        
        # Obtener código y nombre del producto
        codigo = normalizar_texto(fila.get('cod Producto', ''))
        nombre = normalizar_texto(fila.get('Descripcion', ''))
        
        comision_por_unidad = None
        
        # ESTRATEGIA 1: Buscar por código
        if codigo and codigo in tabla_comisiones:
            comision_por_unidad = tabla_comisiones[codigo]
        
        # ESTRATEGIA 2: Buscar por nombre exacto
        elif nombre and nombre in tabla_comisiones:
            comision_por_unidad = tabla_comisiones[nombre]
        
        # ESTRATEGIA 3: Buscar por similitud (fuzzy matching)
        elif nombre:
            comision_simil = buscar_comision_por_similitud(nombre, tabla_comisiones)
            if comision_simil:
                comision_por_unidad = comision_simil
        
        # ESTRATEGIA 4: Buscar por palabras clave
        if comision_por_unidad is None and nombre:
            comision_palabra = buscar_comision_por_palabras_clave(nombre, palabras_clave)
            if comision_palabra:
                comision_por_unidad = comision_palabra
        
        # Si se encontró una comisión, calcular el total
        if comision_por_unidad is not None:
            return float(cantidad) * comision_por_unidad
        
        # No se encontró comisión
        return 0.0
        
    except Exception as e:
        st.warning(f"Error calculando comisión: {e}")
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
def mostrar_productos_sin_comision(df, tabla_comisiones, palabras_clave):
    """
    Identifica y muestra productos que no tienen comisión asignada
    """
    productos_unicos = df['Descripcion'].unique()
    productos_sin_comision = []
    
    for producto in productos_unicos:
        nombre_norm = normalizar_texto(producto)
        tiene_comision = False
        
        # Verificar si tiene comisión por algún método
        if nombre_norm in tabla_comisiones:
            tiene_comision = True
        else:
            # Buscar por similitud
            if buscar_comision_por_similitud(nombre_norm, tabla_comisiones):
                tiene_comision = True
            # Buscar por palabras clave
            elif buscar_comision_por_palabras_clave(nombre_norm, palabras_clave):
                tiene_comision = True
        
        if not tiene_comision:
            productos_sin_comision.append(producto)
    
    return productos_sin_comision

def interfaz_gestion_comisiones(df_base):
    """Interfaz para gestionar comisiones fácilmente"""
    with st.expander("⚙️ Gestión de Comisiones", expanded=False):
        st.subheader("➕ Agregar Nueva Comisión")
        
        col1, col2 = st.columns(2)
        
        with col1:
            nuevo_producto = st.text_input(
                "Nombre del producto (como aparece en Excel):",
                placeholder="Ej: BIDON 20 LT COMB GAS"
            )
        
        with col2:
            nueva_comision = st.number_input(
                "Comisión por unidad ($):",
                min_value=0.0,
                step=100.0,
                format="%.2f"
            )
        
        if st.button("➕ Agregar Comisión", use_container_width=True):
            if nuevo_producto and nueva_comision > 0:
                nombre_normalizado = normalizar_texto(nuevo_producto)
                st.session_state.TABLA_COMISIONES[nombre_normalizado] = nueva_comision
                guardar_comisiones(st.session_state.TABLA_COMISIONES)
                st.success(f"✅ Comisión agregada: {nombre_normalizado} = ${nueva_comision:,.2f}")
                st.rerun()
            else:
                st.error("❌ Por favor completa todos los campos")
        
        st.divider()
        
        st.subheader("🗑️ Eliminar Comisión")
        if len(st.session_state.TABLA_COMISIONES) > 0:
            comision_a_eliminar = st.selectbox(
                "Selecciona comisión para eliminar:",
                options=list(st.session_state.TABLA_COMISIONES.keys())
            )
            
            if st.button("❌ Eliminar Comisión", use_container_width=True):
                if comision_a_eliminar in st.session_state.TABLA_COMISIONES:
                    del st.session_state.TABLA_COMISIONES[comision_a_eliminar]
                    guardar_comisiones(st.session_state.TABLA_COMISIONES)
                    st.success(f"✅ Comisión eliminada: {comision_a_eliminar}")
                    st.rerun()
        else:
            st.info("No hay comisiones configuradas")
        
        st.divider()
        
        st.subheader("📋 Comisiones Configuradas")
        if len(st.session_state.TABLA_COMISIONES) > 0:
            df_comisiones = pd.DataFrame([
                {'Producto/Código': k, 'Comisión por Unidad': f"${v:,.2f}"}
                for k, v in st.session_state.TABLA_COMISIONES.items()
            ])
            st.dataframe(df_comisiones, use_container_width=True, height=300)
        else:
            st.info("No hay comisiones configuradas")
        
        st.divider()
        
        st.subheader("🔍 Diagnosticar Productos Sin Comisión")
        if st.button("🔎 Identificar Productos Sin Comisión", use_container_width=True):
            if df_base is not None and not df_base.empty:
                productos_sin = mostrar_productos_sin_comision(
                    df_base, 
                    st.session_state.TABLA_COMISIONES,
                    PALABRAS_CLAVE_COMISIONES
                )
                
                if productos_sin:
                    st.warning(f"⚠️ Se encontraron {len(productos_sin)} productos sin comisión:")
                    for prod in productos_sin[:20]:
                        st.code(f"• {prod}")
                    
                    if len(productos_sin) > 20:
                        st.info(f"... y {len(productos_sin) - 20} productos más")
                    
                    st.info("💡 Sugerencia: Usa el formulario de arriba para agregar comisiones a estos productos")
                else:
                    st.success("✅ Todos los productos tienen comisión asignada")
            else:
                st.error("❌ Primero carga los archivos de ventas")

def debug_nombres_productos(df):
    """Muestra los nombres reales de productos para depuración"""
    with st.expander("🔧 Debug: Ver Nombres Reales de Productos", expanded=False):
        if 'Descripcion' not in df.columns:
            st.warning("No hay columna 'Descripcion' en los datos")
            return
        
        st.subheader("Nombres de productos en tu Excel")
        
        # Mostrar productos únicos
        productos_unicos = df['Descripcion'].unique()
        
        # Crear DataFrame para mostrar
        df_productos = pd.DataFrame({
            'Nombre en Excel': productos_unicos,
            'Nombre Normalizado': [normalizar_texto(p) for p in productos_unicos],
            'Tiene Comisión': [
                '✅' if (normalizar_texto(p) in st.session_state.TABLA_COMISIONES 
                        or buscar_comision_por_similitud(normalizar_texto(p), st.session_state.TABLA_COMISIONES)
                        or buscar_comision_por_palabras_clave(normalizar_texto(p), PALABRAS_CLAVE_COMISIONES))
                else '❌' 
                for p in productos_unicos
            ]
        })
        
        st.dataframe(df_productos, use_container_width=True, height=400)
        
        # Buscar específicamente productos
        st.subheader("🔍 Buscar productos que contengan texto específico")
        texto_buscar = st.text_input("Buscar:", placeholder="Ej: BIDON, GASOLINA, ACEITE")
        if texto_buscar:
            productos_encontrados = [p for p in productos_unicos if texto_buscar.upper() in normalizar_texto(p)]
            if productos_encontrados:
                for prod in productos_encontrados:
                    nombre_norm = normalizar_texto(prod)
                    st.write(f"• **{prod}**")
                    st.write(f"  Normalizado: {nombre_norm}")
                    
                    # Verificar si tiene comisión
                    if nombre_norm in st.session_state.TABLA_COMISIONES:
                        comision = st.session_state.TABLA_COMISIONES[nombre_norm]
                        st.write(f"  ✅ Comisión asignada: ${comision:,.2f}")
                    else:
                        # Buscar por similitud
                        comision_simil = buscar_comision_por_similitud(nombre_norm, st.session_state.TABLA_COMISIONES)
                        if comision_simil:
                            st.write(f"  ✅ Comisión por similitud: ${comision_simil:,.2f}")
                        else:
                            # Buscar por palabras clave
                            comision_palabra = buscar_comision_por_palabras_clave(nombre_norm, PALABRAS_CLAVE_COMISIONES)
                            if comision_palabra:
                                st.write(f"  ✅ Comisión por palabra clave: ${comision_palabra:,.2f}")
                            else:
                                st.write(f"  ❌ Sin comisión asignada")
                    st.write("---")
            else:
                st.warning(f"No se encontraron productos con '{texto_buscar}'")
                st.info("Los productos disponibles son:")
                for prod in productos_unicos[:10]:
                    st.write(f"• {prod}")

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
    
    # Mostrar errores si los hay (solo los primeros 3)
    if errores:
        for error in errores[:3]:
            st.warning(f"⚠️ {error}")
    
    if lista_df:
        df_final = pd.concat(lista_df, ignore_index=True)
        return df_final, errores
    
    return None, errores
def cargar_archivos_desde_carpeta():
    """Carga automáticamente todos los Excel de la carpeta 'datos/'"""
    
    carpeta_datos = "datos"
    archivos_encontrados = []
    
    # Buscar archivos Excel en la carpeta datos/
    if os.path.exists(carpeta_datos):
        archivos_encontrados = glob.glob(f"{carpeta_datos}/*.xlsx")
        archivos_encontrados.extend(glob.glob(f"{carpeta_datos}/*.xls"))
    
    if not archivos_encontrados:
        return None
    
    lista_df = []
    
    for archivo in archivos_encontrados:
        try:
            # Usar la misma lógica que procesar_archivos
            df_temp = pd.read_excel(archivo, header=None)
            
            # Buscar la fila que contiene 'Fecha' (encabezados)
            header_row = None
            for idx, row in df_temp.iterrows():
                if 'Fecha' in str(row.values):
                    header_row = idx
                    break
            
            if header_row is not None:
                df = pd.read_excel(archivo, skiprows=header_row)
            else:
                df = pd.read_excel(archivo, skiprows=7)
            
            # Limpiar nombres de columnas
            df.columns = [str(c).strip().replace('\n', ' ') for c in df.columns]
            
            # Columnas que necesitamos
            columnas_necesarias = ['Fecha', 'Hora', 'cod Producto', 'Descripcion', 
                                   'Cantidad', 'Valor', 'Nombre Cajero', 'MOP1']
            cols_presentes = [c for c in columnas_necesarias if c in df.columns]
            
            if not cols_presentes:
                st.warning(f"{os.path.basename(archivo)}: No tiene las columnas esperadas")
                continue
            
            df_sel = df[cols_presentes].copy()
            
            # Procesar fechas
            if 'Fecha' in df_sel.columns:
                df_sel['Fecha'] = pd.to_datetime(df_sel['Fecha'], dayfirst=True, errors='coerce')
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
            st.success(f"✅ Procesado: {os.path.basename(archivo)}")
            
        except Exception as e:
            st.error(f"Error en {os.path.basename(archivo)}: {str(e)}")
    
    if lista_df:
        df_final = pd.concat(lista_df, ignore_index=True)
        return df_final
    
    return None
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
# Intentar cargar datos automáticamente al iniciar
if st.session_state.datos_cargados is None:
    with st.spinner('🔄 Cargando archivos desde GitHub...'):
        df_auto = cargar_archivos_desde_carpeta()
        if df_auto is not None:
            st.session_state.datos_cargados = df_auto
            st.session_state.tipo_carga = "automática"
                 # Mostrar información de depuración
            with st.expander("🔍 Información de depuración", expanded=False):
                st.write("Columnas encontradas:", list(df_auto.columns))
                st.write("Primeras filas:", df_auto.head(3))
                st.write("Total registros:", len(df_auto))       

# Panel de opciones de carga
with st.expander("📁 Fuente de datos", expanded=True):
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📂 Datos desde GitHub")
        if st.button("🔄 Recargar datos automáticos", use_container_width=True):
         df_auto = cargar_archivos_desde_carpeta()
    if df_auto is not None:
        st.session_state.datos_cargados = df_auto
        st.session_state.tipo_carga = "automática"
        st.success(f"✅ Cargados {len(df_auto)} registros")
        
        # 👇 AGREGAR ESTO PARA MOSTRAR DIAGNÓSTICO
        with st.expander("📊 Vista previa de datos cargados", expanded=True):
            st.write("**Primeras 5 filas:**")
            st.dataframe(df_auto.head(5))
            st.write("**Columnas encontradas:**", list(df_auto.columns))
        
        st.rerun()  
        
        if os.path.exists("datos"):
            archivos = glob.glob("datos/*.xlsx")
            if archivos:
                st.info(f"📄 Archivos disponibles: {len(archivos)}")
                for a in archivos[:5]:
                    st.caption(f"• {os.path.basename(a)}")
    
    with col2:
        st.markdown("### 💻 Carga manual")
        archivos_subidos = st.file_uploader(
            "Selecciona archivos desde tu computadora", 
            type=['xlsx'], 
            accept_multiple_files=True,
            key="manual_upload"
        )
    
    # =========================================================
    # 👇 AGREGAR EL BOTÓN DE DIAGNÓSTICO AQUÍ (DESPUÉS de las columnas)
    # =========================================================
    
    st.divider()  # Línea separadora opcional
    
    with st.expander("🔧 Diagnóstico de datos", expanded=False):
        if st.button("📊 Ver información de los datos cargados", use_container_width=True):
            if df_base is not None and not df_base.empty:
                st.write("**Columnas disponibles:**")
                st.write(list(df_base.columns))
                st.write("**Primeras 3 filas:**")
                st.dataframe(df_base.head(3))
                st.write("**Tipos de datos:**")
                st.write(df_base.dtypes)
                st.write("**Total de registros:**", len(df_base))
            else:
                st.warning("No hay datos cargados")

# Determinar qué datos usar
# Determinar qué datos usar
if archivos_subidos:
    with st.spinner('Procesando archivos manuales...'):
        df_base, errores = procesar_archivos(archivos_subidos)
        if df_base is not None:
            # Asegurar que los datos tengan las columnas necesarias
            if 'Descripcion' in df_base.columns:
                df_base['Descripcion'] = df_base['Descripcion'].astype(str).str.strip()
            if 'cod Producto' in df_base.columns:
                df_base['cod Producto'] = df_base['cod Producto'].astype(str).str.strip()
            
            st.session_state.datos_cargados = df_base
            st.session_state.tipo_carga = "manual"
            st.success(f"✅ Cargados {len(df_base)} registros manualmente")
elif st.session_state.datos_cargados is not None:
    df_base = st.session_state.datos_cargados
    
    # Asegurar que los datos tengan las columnas necesarias (mismo procesamiento)
    if df_base is not None and not df_base.empty:
        if 'Descripcion' in df_base.columns:
            df_base['Descripcion'] = df_base['Descripcion'].astype(str).str.strip()
        if 'cod Producto' in df_base.columns:
            df_base['cod Producto'] = df_base['cod Producto'].astype(str).str.strip()
    
    if st.session_state.tipo_carga == "automática":
        st.success(f"📊 Usando datos de GitHub ({len(df_base)} registros)")
    else:
        st.info(f"📊 Datos cargados ({len(df_base)} registros)")
else:
    df_base = None
    st.info("👋 No hay datos cargados. Usa 'Recargar datos automáticos' o carga archivos manualmente.")

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
                if 'Fecha' in df_base.columns:
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
        
        # Interfaz de gestión de comisiones
        interfaz_gestion_comisiones(df_base)
        
        # Debug de nombres
        debug_nombres_productos(df_base)
        
        # =========================================================
        # PANEL DE FILTROS COMPLETO
        # =========================================================
        with st.expander("🔍 Panel de Filtros Avanzados", expanded=True):
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
                    st.warning("No hay datos de fecha")
            
            with f2:
                if 'Nombre Cajero' in df_base.columns:
                    vendedores_opciones = sorted(df_base['Nombre Cajero'].unique())
                    vendedores = st.multiselect(
                        "👤 Vendedor:", 
                        vendedores_opciones,
                        default=vendedores_opciones,
                        help="Selecciona uno o más vendedores"
                    )
                else:
                    vendedores = []
                    st.warning("No hay datos de vendedor")
            
            with f3:
                if 'Producto_Info' in df_base.columns:
                    productos_opciones = sorted(df_base['Producto_Info'].unique())
                    productos_sel = st.multiselect(
                        "🛒 Producto (Código - Descripción):", 
                        productos_opciones,
                        default=productos_opciones,
                        help="Selecciona uno o más productos"
                    )
                else:
                    productos_sel = []
                    st.warning("No hay datos de productos")
            
            with f4:
                if 'MOP1' in df_base.columns:
                    mop1_clean = df_base['MOP1'].dropna()
                    if len(mop1_clean) > 0:
                        medios_opciones = sorted(mop1_clean.unique())
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
        
        # =========================================================
        # APLICAR FILTROS
        # =========================================================
        mask = pd.Series([True] * len(df_base))
        
        if len(rango) == 2 and 'Fecha' in df_base.columns:
            mask &= (df_base['Fecha'] >= pd.Timestamp(rango[0])) & \
                    (df_base['Fecha'] <= pd.Timestamp(rango[1]))
        
        if vendedores and 'Nombre Cajero' in df_base.columns:
            mask &= df_base['Nombre Cajero'].isin(vendedores)
        
        if productos_sel and 'Producto_Info' in df_base.columns:
            mask &= df_base['Producto_Info'].isin(productos_sel)
        
        if medios and 'MOP1' in df_base.columns:
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
            
            # Mostrar métricas
            mostrar_metricas(df_filtrado)
            
            st.markdown("---")
            
            # Mostrar gráficos
            crear_graficos(df_filtrado)
            
            # Tabla de resumen por cajero
            with st.expander("💰 Resumen de Liquidación por Cajero", expanded=True):
                if 'Nombre Cajero' in df_filtrado.columns:
                    resumen = df_filtrado.groupby('Nombre Cajero').agg({
                        'Pago_Comision': 'sum',
                        'Valor': 'sum',
                        'Cantidad': 'sum'
                    }).round(2)
                    resumen.columns = ['Total Comisiones', 'Total Ventas', 'Volumen']
                    if 'Total Ventas' in resumen.columns:
                        resumen['% Comisión'] = (resumen['Total Comisiones'] / resumen['Total Ventas'] * 100).round(2)
                    resumen = resumen.sort_values('Total Comisiones', ascending=False)
                    
                    st.dataframe(resumen.style.format({
                        'Total Comisiones': '${:,.0f}',
                        'Total Ventas': '${:,.0f}',
                        'Volumen': '{:,.1f}',
                        '% Comisión': '{:.2f}%'
                    }), use_container_width=True)
                else:
                    st.info("No hay datos de vendedores")
            
            # Resumen de comisiones por producto
            with st.expander("📊 Resumen de Comisiones por Producto"):
                if 'Descripcion' in df_filtrado.columns:
                    resumen_comisiones = df_filtrado.groupby('Descripcion').agg({
                        'Cantidad': 'sum',
                        'Pago_Comision': 'sum',
                        'Valor': 'sum'
                    }).round(2)
                    resumen_comisiones = resumen_comisiones[resumen_comisiones['Pago_Comision'] > 0]
                    resumen_comisiones = resumen_comisiones.sort_values('Pago_Comision', ascending=False)
                    
                    if not resumen_comisiones.empty:
                        st.dataframe(resumen_comisiones.style.format({
                            'Cantidad': '{:,.1f}',
                            'Pago_Comision': '${:,.0f}',
                            'Valor': '${:,.0f}'
                        }), use_container_width=True)
                    else:
                        st.warning("⚠️ No se encontraron comisiones calculadas para ningún producto")
                        st.info("💡 Verifica que los productos tengan comisión asignada en la sección 'Gestión de Comisiones'")
                else:
                    st.info("No hay datos de productos")
            
            # Detalle de transacciones
            with st.expander("📋 Ver detalle de todas las transacciones"):
                columnas_mostrar = ['Fecha', 'Hora', 'Nombre Cajero', 'Producto_Info', 'Cantidad', 'Valor', 'Pago_Comision']
                columnas_disponibles = [col for col in columnas_mostrar if col in df_filtrado.columns]
                
                if columnas_disponibles:
                    st.dataframe(
                        df_filtrado[columnas_disponibles].style.format({
                            'Valor': '${:,.0f}',
                            'Pago_Comision': '${:,.0f}',
                            'Cantidad': '{:,.1f}'
                        }),
                        use_container_width=True,
                        height=400
                    )
                else:
                    st.info("No hay columnas para mostrar")
            
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
            """)

else:
    st.info("👋 **Bienvenido al Sistema de Gestión de Ventas**\n\nPor favor, selecciona tus archivos Excel 'Ventas_*.xlsx' para comenzar a analizar tus datos.")
    
    with st.expander("📖 Ver ejemplo de uso"):
        st.markdown("""
        ### ¿Cómo usar esta aplicación?
        
        1. **Prepara tus archivos Excel** con el formato de ventas de tu estación
        2. **Carga uno o varios archivos** usando el botón de arriba
        3. **Aplica filtros** para analizar periodos específicos, vendedores o productos
        4. **Visualiza métricas** y gráficos automáticos
        5. **Exporta reportes** a Excel con un solo clic
        """)

# =========================================================
# 6. FOOTER
# =========================================================
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray; font-size: 12px;'>"
    "© 2024 Estación Pro - Sistema de Gestión de Ventas | "
    "Las comisiones se guardan automáticamente en 'comisiones_guardadas.json'"
    "</div>",
    unsafe_allow_html=True
)