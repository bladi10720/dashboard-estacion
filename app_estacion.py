import streamlit as st
import pandas as pd
import plotly.express as px
import io
import re
import json
import os
from datetime import datetime
from difflib import get_close_matches

# =========================================================
# 1. CONFIGURACIÓN DE COMISIONES CON PERSISTENCIA
# =========================================================

ARCHIVO_COMISIONES = "comisiones_guardadas.json"

def cargar_comisiones():
    """Carga las comisiones desde un archivo JSON"""
    comisiones_por_defecto = {
        # Códigos
        '966879': 1000.0,
        '102': 8.0,
        '1050': 15.0,
        
        # Nombres exactos
        'GASOLINA 97': 10.0,
        'DIESEL': 4.0,
        'KEROSENE': 6.0,
        'ACEITE MOTOR': 500.0,
        'ADBLUE': 16.0,
        'DIXSEL': 100.0,
        'PETROLEO DIESEL G-B': 100.0,
        'GASOLINA 93': 1000.0,
        'GASOLINA 95': 8.0,
        
        # Bidón 20 litros
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
                # Combinar comisiones por defecto con las guardadas
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
if 'TABLA_COMISIONES' not in st.session_state:
    st.session_state.TABLA_COMISIONES = cargar_comisiones()

# Palabras clave para búsqueda flexible (también persistentes)
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
    """Calcula comisión con múltiples estrategias"""
    try:
        cantidad = fila.get('Cantidad', 0)
        if pd.isna(cantidad) or cantidad <= 0:
            return 0.0
        
        codigo = normalizar_texto(fila.get('cod Producto', ''))
        nombre = normalizar_texto(fila.get('Descripcion', ''))
        
        comision_por_unidad = None
        
        # Estrategia 1: Por código
        if codigo and codigo in tabla_comisiones:
            comision_por_unidad = tabla_comisiones[codigo]
        
        # Estrategia 2: Por nombre exacto
        elif nombre and nombre in tabla_comisiones:
            comision_por_unidad = tabla_comisiones[nombre]
        
        # Estrategia 3: Por similitud
        elif nombre:
            comision_simil = buscar_comision_por_similitud(nombre, tabla_comisiones)
            if comision_simil:
                comision_por_unidad = comision_simil
        
        # Estrategia 4: Por palabras clave
        if comision_por_unidad is None and nombre:
            comision_palabra = buscar_comision_por_palabras_clave(nombre, palabras_clave)
            if comision_palabra:
                comision_por_unidad = comision_palabra
        
        if comision_por_unidad is not None:
            return float(cantidad) * comision_por_unidad
        
        return 0.0
        
    except Exception as e:
        return 0.0

def validar_datos(df):
    """Valida la calidad de los datos cargados"""
    if df is None or df.empty:
        return False, "No hay datos para procesar"
    
    problemas = []
    columnas_requeridas = ['Fecha', 'Cantidad', 'Valor']
    for col in columnas_requeridas:
        if col not in df.columns:
            problemas.append(f"Falta columna: {col}")
    
    if problemas:
        return False, "; ".join(problemas)
    
    return True, "Datos válidos"

def mostrar_metricas(df):
    """Muestra métricas con formato profesional"""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("💰 Recaudación Total", f"${df['Valor'].sum():,.0f}")
    with col2:
        st.metric("💵 Comisiones a Pagar", f"${df['Pago_Comision'].sum():,.0f}")
    with col3:
        st.metric("⛽ Litros/Unidades", f"{df['Cantidad'].sum():,.1f}")
    with col4:
        st.metric("📊 N° de Ventas", f"{len(df):,}")

def crear_graficos(df_filtrado):
    """Crea gráficos interactivos"""
    tab1, tab2, tab3 = st.tabs(["📊 Por Hora", "📈 Tendencia", "🥧 Por Producto"])
    
    with tab1:
        if 'Hora' in df_filtrado.columns:
            df_filtrado['Hora_H'] = df_filtrado['Hora'].astype(str).str[:2]
            ventas_hora = df_filtrado.groupby('Hora_H')['Valor'].sum().reset_index()
            fig_h = px.bar(ventas_hora, x='Hora_H', y='Valor', 
                          title="Ventas por Hora",
                          color_discrete_sequence=['#004b87'])
            st.plotly_chart(fig_h, use_container_width=True)
    
    with tab2:
        if len(df_filtrado) > 1:
            ventas_dia = df_filtrado.groupby('Fecha')['Valor'].sum().reset_index()
            fig_line = px.line(ventas_dia, x='Fecha', y='Valor',
                              title="Evolución de Ventas", markers=True)
            st.plotly_chart(fig_line, use_container_width=True)
    
    with tab3:
        top_productos = df_filtrado.groupby('Descripcion')['Valor'].sum().nlargest(10)
        if len(top_productos) > 0:
            fig_pie = px.pie(values=top_productos.values, 
                            names=top_productos.index,
                            title="Top 10 Productos")
            st.plotly_chart(fig_pie, use_container_width=True)

def exportar_reporte(df):
    """Exporta el reporte a Excel"""
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_detalle = df[['Fecha', 'Hora', 'Nombre Cajero', 'Descripcion', 
                        'Cantidad', 'Valor', 'Pago_Comision']].copy()
        df_detalle.to_excel(writer, sheet_name='Detalle Ventas', index=False)
        
        resumen_cajero = df.groupby('Nombre Cajero').agg({
            'Valor': 'sum',
            'Pago_Comision': 'sum',
            'Cantidad': 'sum'
        }).round(2)
        resumen_cajero.to_excel(writer, sheet_name='Resumen por Cajero')
    
    return output.getvalue()

def mostrar_productos_sin_comision(df, tabla_comisiones, palabras_clave):
    """Identifica productos sin comisión"""
    productos_unicos = df['Descripcion'].unique()
    productos_sin_comision = []
    
    for producto in productos_unicos:
        nombre_norm = normalizar_texto(producto)
        tiene_comision = False
        
        if nombre_norm in tabla_comisiones:
            tiene_comision = True
        elif buscar_comision_por_similitud(nombre_norm, tabla_comisiones):
            tiene_comision = True
        elif buscar_comision_por_palabras_clave(nombre_norm, palabras_clave):
            tiene_comision = True
        
        if not tiene_comision:
            productos_sin_comision.append(producto)
    
    return productos_sin_comision

def interfaz_gestion_comisiones(df_base):
    """Interfaz para gestionar comisiones (ahora con guardado)"""
    with st.expander("⚙️ Gestión de Comisiones", expanded=False):
        st.subheader("➕ Agregar Nueva Comisión")
        
        col1, col2 = st.columns(2)
        
        with col1:
            nuevo_producto = st.text_input(
                "Nombre del producto:",
                placeholder="Ej: BIDON 20 LT COMB GAS",
                key="nuevo_producto_input"
            )
        
        with col2:
            nueva_comision = st.number_input(
                "Comisión por unidad ($):",
                min_value=0.0,
                step=100.0,
                format="%.2f",
                key="nueva_comision_input"
            )
        
        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
        with col_btn2:
            if st.button("💾 Guardar Comisión", use_container_width=True):
                if nuevo_producto and nueva_comision > 0:
                    nombre_normalizado = normalizar_texto(nuevo_producto)
                    st.session_state.TABLA_COMISIONES[nombre_normalizado] = nueva_comision
                    
                    # Guardar en archivo
                    if guardar_comisiones(st.session_state.TABLA_COMISIONES):
                        st.success(f"✅ Comisión guardada: {nombre_normalizado} = ${nueva_comision:,.2f}")
                        st.rerun()
                    else:
                        st.error("❌ Error al guardar la comisión")
                else:
                    st.error("❌ Completa todos los campos")
        
        st.divider()
        
        st.subheader("🗑️ Eliminar Comisión")
        comision_a_eliminar = st.selectbox(
            "Selecciona comisión para eliminar:",
            options=list(st.session_state.TABLA_COMISIONES.keys()),
            key="eliminar_comision_select"
        )
        
        if st.button("❌ Eliminar Comisión", use_container_width=True):
            if comision_a_eliminar in st.session_state.TABLA_COMISIONES:
                del st.session_state.TABLA_COMISIONES[comision_a_eliminar]
                guardar_comisiones(st.session_state.TABLA_COMISIONES)
                st.success(f"✅ Comisión eliminada: {comision_a_eliminar}")
                st.rerun()
        
        st.divider()
        
        st.subheader("📋 Comisiones Configuradas")
        df_comisiones = pd.DataFrame([
            {'Producto/Código': k, 'Comisión por Unidad': f"${v:,.2f}"}
            for k, v in st.session_state.TABLA_COMISIONES.items()
        ])
        st.dataframe(df_comisiones, use_container_width=True, height=300)
        
        st.divider()
        
        st.subheader("🔍 Diagnosticar Productos Sin Comisión")
        if st.button("🔎 Identificar Productos Sin Comisión", use_container_width=True):
            if df_base is not None:
                productos_sin = mostrar_productos_sin_comision(
                    df_base, 
                    st.session_state.TABLA_COMISIONES,
                    PALABRAS_CLAVE_COMISIONES
                )
                
                if productos_sin:
                    st.warning(f"⚠️ {len(productos_sin)} productos sin comisión:")
                    for prod in productos_sin[:20]:
                        st.code(f"• {prod}")
                    
                    st.info("💡 Usa el formulario para agregar comisiones")
                else:
                    st.success("✅ Todos los productos tienen comisión")
            else:
                st.error("❌ Carga archivos primero")

def debug_nombres_productos(df):
    """Muestra nombres reales para depuración"""
    with st.expander("🔧 Debug: Ver Nombres Reales", expanded=False):
        productos_unicos = df['Descripcion'].unique()
        
        df_productos = pd.DataFrame({
            'Nombre en Excel': productos_unicos,
            'Nombre Normalizado': [normalizar_texto(p) for p in productos_unicos],
            'Tiene Comisión': [
                '✅' if (normalizar_texto(p) in st.session_state.TABLA_COMISIONES or
                        buscar_comision_por_similitud(normalizar_texto(p), st.session_state.TABLA_COMISIONES) or
                        buscar_comision_por_palabras_clave(normalizar_texto(p), PALABRAS_CLAVE_COMISIONES))
                else '❌' 
                for p in productos_unicos
            ]
        })
        
        st.dataframe(df_productos, use_container_width=True, height=400)
        
        # Buscar productos específicos
        st.subheader("🔍 Buscar productos que contengan texto específico")
        texto_buscar = st.text_input("Buscar:", placeholder="BIDON")
        if texto_buscar:
            productos_encontrados = [p for p in productos_unicos if texto_buscar.upper() in normalizar_texto(p)]
            if productos_encontrados:
                for prod in productos_encontrados:
                    st.write(f"• **{prod}**")
            else:
                st.warning("No se encontraron productos")

# =========================================================
# 3. CARGA DE DATOS
# =========================================================
@st.cache_data
def procesar_archivos(lista_archivos):
    columnas_posibles = ['Fecha', 'Hora', 'cod Producto', 'Descripcion', 
                        'Cantidad', 'Valor', 'Nombre Cajero', 'MOP1']
    lista_df = []
    errores = []
    
    for arc in lista_archivos:
        try:
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
            
            lista_df.append(df_sel)
            
        except Exception as e:
            errores.append(f"{arc.name}: {str(e)}")
    
    if lista_df:
        return pd.concat(lista_df, ignore_index=True), errores
    return None, errores

# =========================================================
# 4. CONFIGURACIÓN DE LA PÁGINA
# =========================================================
st.set_page_config(page_title="Estación Pro - Reportes", layout="wide", page_icon="⛽")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    [data-testid="stMetricValue"] { font-size: 28px; color: #004b87; }
    </style>
    """, unsafe_allow_html=True)

st.title("⛽ Sistema de Gestión de Ventas - Estación Pro")
st.markdown("---")

# =========================================================
# 5. CUERPO PRINCIPAL
# =========================================================
archivos_subidos = st.file_uploader(
    "📂 Selecciona tus archivos Excel", 
    type=['xlsx'], 
    accept_multiple_files=True
)

if archivos_subidos:
    with st.spinner('🔄 Procesando...'):
        df_base, errores = procesar_archivos(archivos_subidos)
    
    if df_base is not None and not df_base.empty:
        st.success(f"✅ {len(df_base)} registros cargados")
        
        # Procesar datos
        if 'cod Producto' in df_base.columns:
            df_base['cod Producto'] = df_base['cod Producto'].astype(str).str.strip()
        
        df_base['Descripcion'] = df_base['Descripcion'].astype(str).str.strip()
        
        if 'cod Producto' in df_base.columns:
            df_base['Producto_Info'] = df_base['cod Producto'] + " - " + df_base['Descripcion']
        else:
            df_base['Producto_Info'] = df_base['Descripcion']
        
        # Gestión de comisiones (persistente)
        interfaz_gestion_comisiones(df_base)
        
        # Debug
        debug_nombres_productos(df_base)
        
        # Filtros
        with st.expander("🔍 Filtros", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                fecha_min = df_base['Fecha'].min()
                fecha_max = df_base['Fecha'].max()
                rango = st.date_input("Periodo:", [fecha_min, fecha_max])
            
            with col2:
                vendedores = st.multiselect("Vendedor:", df_base['Nombre Cajero'].unique())
        
        # Aplicar filtros
        mask = pd.Series([True] * len(df_base))
        if vendedores:
            mask &= df_base['Nombre Cajero'].isin(vendedores)
        if len(rango) == 2:
            mask &= (df_base['Fecha'] >= pd.Timestamp(rango[0])) & \
                    (df_base['Fecha'] <= pd.Timestamp(rango[1]))
        
        df_filtrado = df_base.loc[mask].copy()
        
        if df_filtrado.empty:
            st.warning("⚠️ No hay datos con los filtros seleccionados")
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
            
            # Mostrar resultados
            mostrar_metricas(df_filtrado)
            st.markdown("---")
            crear_graficos(df_filtrado)
            
            # Resumen por vendedor
            with st.expander("💰 Resumen por Vendedor", expanded=True):
                resumen = df_filtrado.groupby('Nombre Cajero').agg({
                    'Pago_Comision': 'sum',
                    'Valor': 'sum',
                    'Cantidad': 'sum'
                }).round(2)
                resumen.columns = ['Comisiones', 'Ventas', 'Volumen']
                st.dataframe(resumen.style.format({
                    'Comisiones': '${:,.0f}',
                    'Ventas': '${:,.0f}'
                }), use_container_width=True)
            
            # Detalle
            with st.expander("📋 Ver detalle"):
                st.dataframe(df_filtrado[[
                    'Fecha', 'Hora', 'Nombre Cajero', 'Producto_Info', 
                    'Cantidad', 'Valor', 'Pago_Comision'
                ]], use_container_width=True, height=400)
            
            # Exportar
            if st.button("📥 Exportar a Excel"):
                excel_data = exportar_reporte(df_filtrado)
                st.download_button(
                    label="💾 Descargar",
                    data=excel_data,
                    file_name=f"reporte_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    
    else:
        st.error("❌ Error al procesar archivos")
else:
    st.info("👋 Selecciona tus archivos Excel para comenzar")

# =========================================================
# 6. FOOTER
# =========================================================
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray; font-size: 12px;'>"
    "© 2024 Estación Pro - Las comisiones se guardan automáticamente"
    "</div>",
    unsafe_allow_html=True
)