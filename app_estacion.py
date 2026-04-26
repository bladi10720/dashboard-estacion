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
# UI/UX helpers (sin tocar lógica de negocio)
# =========================================================

MESES_ES = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}

def _extraer_mes_desde_nombre_archivo(nombre_archivo: str):
    """Intenta inferir el mes (1-12) desde el nombre del Excel."""
    if not nombre_archivo:
        return None
    base = os.path.splitext(os.path.basename(str(nombre_archivo)))[0]
    txt = normalizar_texto(base)
    txt = txt.replace(" ", "")

    # Buscar coincidencias por nombre (ES) primero
    for m_num, m_name in MESES_ES.items():
        if normalizar_texto(m_name).replace(" ", "") in txt:
            return m_num

    # Buscar patrón numérico tipo 02, 2, 2026-02, etc.
    match = re.search(r'(?<!\d)(0?[1-9]|1[0-2])(?!\d)', txt)
    if match:
        try:
            m = int(match.group(1))
            if 1 <= m <= 12:
                return m
        except Exception:
            return None
    return None

def _mes_num_a_label(mes_num: int):
    if mes_num in MESES_ES:
        return MESES_ES[mes_num].capitalize()
    return "Todos"

def _render_selector_vendedores_cards(vendedores_opciones, max_cards=10):
    """Selector visual por tarjetas (buttons) con estado."""
    if 'vendedor_seleccionado' not in st.session_state:
        st.session_state.vendedor_seleccionado = "Todos"

    # Normalizar opciones
    vendedores_opciones = [v for v in vendedores_opciones if v and str(v).strip()]
    vendedores_opciones = convertir_a_string(vendedores_opciones)

    # Búsqueda para no limitar la selección real a 10
    busqueda = st.text_input("Buscar vendedor", value="", placeholder="Escribe para filtrar…")
    if busqueda.strip():
        b = normalizar_texto(busqueda).replace(" ", "")
        filtrados = []
        for v in vendedores_opciones:
            vn = normalizar_texto(v).replace(" ", "")
            if b in vn:
                filtrados.append(v)
        vendors_for_cards = filtrados[:max_cards]
    else:
        vendors_for_cards = vendedores_opciones[:max_cards]

    # Tarjetas en grid
    cols = st.columns(5)  # responsive-ish; en móvil se apila

    def _btn_label(v):
        selected = (st.session_state.vendedor_seleccionado == v)
        return f"✅ {v}" if selected else v

    # Botón "Todos" siempre visible
    with cols[0]:
        if st.button(_btn_label("Todos"), use_container_width=True, key="vend_card_todos"):
            st.session_state.vendedor_seleccionado = "Todos"
            st.rerun()

    # Resto de tarjetas (máx. 10)
    for i, v in enumerate(vendors_for_cards):
        col = cols[(i + 1) % 5]
        with col:
            if st.button(_btn_label(v), use_container_width=True, key=f"vend_card_{i}_{v}"):
                st.session_state.vendedor_seleccionado = v
                st.rerun()

    # Estado actual
    st.caption(f"Seleccionado: **{st.session_state.vendedor_seleccionado}**")

def _kpis_vendedor(df, vendedor_seleccionado: str):
    """KPIs para vendedor seleccionado (usa df ya filtrado por mes/fecha/producto/medio)."""
    if df is None or df.empty:
        return
    if vendedor_seleccionado and vendedor_seleccionado != "Todos" and 'Nombre Cajero' in df.columns:
        df_kpi = df[df['Nombre Cajero'] == vendedor_seleccionado]
    else:
        df_kpi = df

    total_ventas = float(df_kpi['Valor'].sum()) if 'Valor' in df_kpi.columns else 0.0
    total_comisiones = float(df_kpi['Pago_Comision'].sum()) if 'Pago_Comision' in df_kpi.columns else 0.0
    n_ventas = int(len(df_kpi))
    ticket_prom = (total_ventas / n_ventas) if n_ventas > 0 else 0.0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Ventas (selección)", f"${total_ventas:,.0f}")
    with c2:
        st.metric("Comisiones", f"${total_comisiones:,.0f}")
    with c3:
        st.metric("Transacciones", f"{n_ventas:,}")
    with c4:
        st.metric("Ticket promedio", f"${ticket_prom:,.0f}")

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
    .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
    [data-testid="stHorizontalBlock"] { gap: 1rem; }
    </style>
    """, unsafe_allow_html=True)

top = st.container()
with top:
    st.title("⛽ Estación Pro · Dashboard de Ventas y Comisiones")
    st.caption("Interfaz optimizada tipo empresa (Power BI / Tableau) · Datos desde carpeta `datos/` o carga manual")
    st.divider()

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
    """Calcula comisión buscando primero por código, luego por nombre"""
    try:
        cantidad = fila.get('Cantidad', 0)
        if pd.isna(cantidad) or cantidad <= 0:
            return 0.0
        
        # 1. BUSCAR POR CÓDIGO (prioridad máxima)
        codigo = normalizar_texto(fila.get('Cod Producto', ''))
        if codigo and codigo in tabla_comisiones:
            return float(cantidad) * tabla_comisiones[codigo]
        
        # 2. BUSCAR POR NOMBRE
        nombre = normalizar_texto(fila.get('Descripcion', ''))
        if nombre and nombre in tabla_comisiones:
            return float(cantidad) * tabla_comisiones[nombre]
        
        # 3. BUSCAR POR PALABRAS CLAVE
        if nombre:
            for palabra, comision in palabras_clave.items():
                if palabra in nombre:
                    return float(cantidad) * comision
        
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
    col_g1, col_g2 = st.columns([2, 1])

    with col_g1:
        st.subheader("📈 Ventas por día")
        if len(df) > 1 and 'Fecha' in df.columns:
            ventas_dia = df.groupby('Fecha', as_index=False)['Valor'].sum()
            fig = px.line(
                ventas_dia,
                x='Fecha',
                y='Valor',
                markers=True,
                title=None,
                color_discrete_sequence=['#004b87']
            )
            fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay suficientes datos para ventas por día.")

    with col_g2:
        st.subheader("🏆 Ranking vendedores (mes)")
        if 'Nombre Cajero' in df.columns:
            ranking = df.groupby('Nombre Cajero', as_index=False)['Valor'].sum().sort_values('Valor', ascending=False).head(15)
            if not ranking.empty:
                fig = px.bar(
                    ranking.sort_values('Valor', ascending=True),
                    x='Valor',
                    y='Nombre Cajero',
                    orientation='h',
                    title=None,
                    color_discrete_sequence=['#1f77b4']
                )
                fig.update_layout(margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No hay ranking para mostrar.")
        else:
            st.info("No hay columna de vendedor para ranking.")

    st.subheader("📊 Ventas por producto")
    if 'Descripcion' in df.columns:
        top_prod = df.groupby('Descripcion', as_index=False)['Valor'].sum().sort_values('Valor', ascending=False).head(20)
        if not top_prod.empty:
            fig = px.bar(
                top_prod,
                x='Descripcion',
                y='Valor',
                title=None,
                color_discrete_sequence=['#004b87']
            )
            fig.update_layout(margin=dict(l=10, r=10, t=10, b=10))
            fig.update_xaxes(tickangle=35)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay ventas por producto para mostrar.")
    else:
        st.info("No hay columna de producto para mostrar.")

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
    columnas_posibles = ['Fecha', 'Hora', 'Cod Producto', 'Descripcion', 
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
        
        # MOSTRAR DIAGNÓSTICO
        st.write("---")
        st.write("### 🔍 Diagnóstico de COMISION.xlsx")
        st.write(f"**Columnas encontradas:** {list(df.columns)}")
        st.write("**Primeras 5 filas:**")
        st.dataframe(df.head(5))
        
        # BUSCAR las columnas que tienen datos (no vacías)
        col_codigo = None
        col_comision = None
        
        for col in df.columns:
            # Verificar si la columna tiene algún valor no vacío
            if df[col].notna().any():
                # Revisar el primer valor no vacío
                primer_valor = df[col].dropna().iloc[0] if len(df[col].dropna()) > 0 else ""
                primer_valor_str = str(primer_valor).upper()
                
                # Si parece un código (número o texto)
                if col_codigo is None and (primer_valor_str.isdigit() or len(primer_valor_str) < 10):
                    col_codigo = col
                # Si parece una comisión (número)
                elif col_comision is None and isinstance(primer_valor, (int, float)):
                    col_comision = col
        
        # Si no encontró automáticamente, usar columnas 2 y 3 (índices 2 y 3)
        if col_codigo is None and len(df.columns) > 2:
            col_codigo = df.columns[2]
        if col_comision is None and len(df.columns) > 3:
            col_comision = df.columns[3]
        
        st.write(f"**Usando columna '{col_codigo}' para códigos**")
        st.write(f"**Usando columna '{col_comision}' para comisiones**")
        
        comisiones = {}
        
        for idx, row in df.iterrows():
            if col_codigo and col_comision:
                codigo = str(row[col_codigo]).strip()
                comision = row[col_comision]
                
                # Mostrar algunas filas
                if idx < 5:
                    st.write(f"Fila {idx}: Código='{codigo}', Comisión={comision}")
                
                # Validar
                if pd.notna(codigo) and pd.notna(comision) and codigo != 'nan' and comision != 0:
                    try:
                        comisiones[codigo] = float(comision)
                    except:
                        pass
        
        st.write(f"**Total de comisiones válidas encontradas:** {len(comisiones)}")
        st.write("---")
        
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
    if 'Cod Producto' in df_base.columns:
        df_base['Cod Producto'] = df_base['Cod Producto'].astype(str).str.strip()
    df_base['Descripcion'] = df_base['Descripcion'].astype(str).str.strip()
    
    if 'Cod Producto' in df_base.columns:
        df_base['Producto_Info'] = df_base['Cod Producto'] + " - " + df_base['Descripcion']
    else:
        df_base['Producto_Info'] = df_base['Descripcion']
    
    # Gestión de comisiones
    interfaz_gestion_comisiones()
    
    # =========================================================
    # FILTROS DINÁMICOS
    # =========================================================
    filtros = st.container()
    with filtros:
        st.subheader("🔎 Filtros")
        with st.expander("Ajustar filtros", expanded=True):
            f0, f1, f3, f4 = st.columns([1, 2, 2, 2])
            
            with f0:
                # Filtro por mes (basado en archivos Excel y/o fechas)
                meses_detectados = set()
                if archivos_subidos:
                    for a in archivos_subidos:
                        m = _extraer_mes_desde_nombre_archivo(getattr(a, "name", ""))
                        if m:
                            meses_detectados.add(m)
                else:
                    if os.path.exists("datos"):
                        for p in glob.glob("datos/*.xlsx"):
                            if os.path.basename(p).upper() == "COMISION.XLSX":
                                continue
                            m = _extraer_mes_desde_nombre_archivo(p)
                            if m:
                                meses_detectados.add(m)
                
                # Fallback si no hay meses por nombre: usar meses presentes en Fecha
                if 'Fecha' in df_base.columns:
                    try:
                        meses_en_datos = set(int(m) for m in df_base['Fecha'].dropna().dt.month.unique())
                        meses_detectados |= meses_en_datos
                    except Exception:
                        pass
                
                opciones_mes = ["Todos"] + [_mes_num_a_label(m) for m in sorted(meses_detectados)]
                if 'mes_seleccionado' not in st.session_state:
                    st.session_state.mes_seleccionado = "Todos"
                
                mes_sel = st.selectbox(
                    "Mes",
                    options=opciones_mes if opciones_mes else ["Todos"],
                    index=(opciones_mes.index(st.session_state.mes_seleccionado) if st.session_state.mes_seleccionado in opciones_mes else 0),
                )
                st.session_state.mes_seleccionado = mes_sel
        
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
        
        with f3:
            # -------------------------
            # 🛒 PRODUCTOS (UX mejorada)
            # -------------------------
            if 'Producto_Info' in df_base.columns:
                # Todas las opciones (orden alfabético)
                productos_series = df_base['Producto_Info'].dropna().astype(str).str.strip()
                productos_all = sorted(convertir_a_string(productos_series.unique()), key=lambda x: x.lower())

                # Top 20 más usados (sugerencias)
                top20 = productos_series.value_counts().head(20).index.tolist()
                top20 = [str(x).strip() for x in top20 if pd.notna(x)]

                # Búsqueda rápida
                st.markdown("**🛒 Productos**")
                if len(productos_all) > 80:
                    st.caption(f"Escribe para buscar entre los **{len(productos_all)}** productos.")
                q_prod = st.text_input(
                    "Búsqueda rápida de producto",
                    value=st.session_state.get("filtro_busqueda_producto", ""),
                    placeholder="Ej: GAS, BIDON, 95, 97…",
                    key="filtro_busqueda_producto",
                    label_visibility="collapsed",
                )

                # Botones rápidos
                b1, b2 = st.columns(2)
                with b1:
                    if st.button("Seleccionar todos", use_container_width=True, key="btn_prod_all"):
                        st.session_state.productos_seleccionados = list(productos_all)
                        st.rerun()
                with b2:
                    if st.button("Limpiar", use_container_width=True, key="btn_prod_clear"):
                        st.session_state.productos_seleccionados = []
                        st.rerun()

                # Filtrar por búsqueda (sin complejidad)
                if q_prod and q_prod.strip():
                    qn = normalizar_texto(q_prod).replace(" ", "")
                    productos_filtrados = [p for p in productos_all if qn in normalizar_texto(p).replace(" ", "")]
                else:
                    productos_filtrados = productos_all

                # Orden: sugerencias primero (top 20), luego el resto alfabético
                top20_set = set(top20)
                sugerencias = [p for p in top20 if p in productos_filtrados]
                resto = [p for p in productos_filtrados if p not in top20_set]
                productos_opciones = sugerencias + resto

                # Persistencia de selección
                if "productos_seleccionados" not in st.session_state:
                    st.session_state.productos_seleccionados = list(productos_all)

                # Validación: no permitir vacío
                default_prod = [p for p in st.session_state.productos_seleccionados if p in productos_opciones]
                if not default_prod and productos_opciones:
                    default_prod = list(productos_opciones)

                productos = st.multiselect(
                    "🛒 Producto:",
                    options=productos_opciones,
                    default=default_prod,
                    help="Sugerencias: los 20 productos más usados aparecen primero.",
                )

                st.session_state.productos_seleccionados = list(productos)
                if len(productos) == 0 and len(productos_all) > 0:
                    st.warning("Selecciona al menos un producto. Se restauró la selección completa.")
                    st.session_state.productos_seleccionados = list(productos_all)
                    productos = list(productos_all)
                    st.rerun()
            else:
                productos = []

        with f4:
            # ------------------------------
            # 💳 MÉTODOS DE PAGO (UX mejorada)
            # ------------------------------
            if 'MOP1' in df_base.columns:
                mop_series = df_base['MOP1'].dropna().astype(str).str.strip()
                if len(mop_series) > 0:
                    freq = mop_series.value_counts()
                    medios_all = freq.index.tolist()  # ya ordenado por frecuencia

                    def _icono_mop(nombre: str):
                        n = normalizar_texto(nombre)
                        if "EFECTIVO" in n or "CASH" in n:
                            return "💵"
                        if "TARJ" in n or "CRED" in n or "DEB" in n or "VISA" in n or "MAST" in n:
                            return "💳"
                        if "TRANSF" in n or "TRANSFER" in n or "BANCO" in n:
                            return "🏦"
                        return "💳"

                    medios_labels = {m: f"{_icono_mop(m)} {m}" for m in medios_all}
                    medios_opciones = [medios_labels[m] for m in medios_all]

                    st.markdown("**💳 Métodos de pago**")
                    b1, b2 = st.columns(2)
                    with b1:
                        if st.button("Seleccionar todos", use_container_width=True, key="btn_mop_all"):
                            st.session_state.medios_seleccionados = list(medios_all)
                            st.rerun()
                    with b2:
                        if st.button("Limpiar", use_container_width=True, key="btn_mop_clear"):
                            st.session_state.medios_seleccionados = []
                            st.rerun()

                    if "medios_seleccionados" not in st.session_state:
                        st.session_state.medios_seleccionados = list(medios_all)

                    # Defaults mapeados a labels
                    default_medios = [medios_labels[m] for m in st.session_state.medios_seleccionados if m in medios_labels]
                    if not default_medios and len(medios_opciones) > 0:
                        default_medios = list(medios_opciones)

                    medios_labels_sel = st.multiselect(
                        "💳 Método de Pago:",
                        options=medios_opciones,
                        default=default_medios,
                        help="Ordenados por uso (frecuencia).",
                    )

                    # Convertir labels seleccionados a valores originales (compatibilidad con filtro existente)
                    inv = {v: k for k, v in medios_labels.items()}
                    medios = [inv[x] for x in medios_labels_sel if x in inv]

                    st.session_state.medios_seleccionados = list(medios)
                    if len(medios) == 0 and len(medios_all) > 0:
                        st.warning("Selecciona al menos un método de pago. Se restauró la selección completa.")
                        st.session_state.medios_seleccionados = list(medios_all)
                        medios = list(medios_all)
                        st.rerun()
                else:
                    medios = []
            else:
                medios = []

        # Selector de vendedor tipo tarjetas (reemplaza selectores de vendedor)
        if 'Nombre Cajero' in df_base.columns:
            st.markdown("#### 👤 Vendedor (tarjetas)")
            _render_selector_vendedores_cards(df_base['Nombre Cajero'].unique(), max_cards=10)
        else:
            st.info("No hay columna de vendedor para seleccionar.")
    # =========================================================
    # APLICAR FILTROS
    # =========================================================
    mask = pd.Series([True] * len(df_base))
    
    # Filtro por mes (si hay fecha)
    if 'Fecha' in df_base.columns and st.session_state.get("mes_seleccionado", "Todos") != "Todos":
        try:
            mes_label = st.session_state.mes_seleccionado.strip().lower()
            mes_num = None
            for m, name in MESES_ES.items():
                if name == mes_label:
                    mes_num = m
                    break
            if mes_num:
                mask &= (df_base['Fecha'].dt.month == mes_num)
        except Exception:
            pass
    
    if 'rango' in locals() and len(rango) == 2:
        mask &= (df_base['Fecha'] >= pd.Timestamp(rango[0])) & \
                (df_base['Fecha'] <= pd.Timestamp(rango[1]))
    
    vendedor_sel = st.session_state.get("vendedor_seleccionado", "Todos")
    if vendedor_sel and vendedor_sel != "Todos" and 'Nombre Cajero' in df_base.columns:
        mask &= (df_base['Nombre Cajero'] == vendedor_sel)
    
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
        st.divider()

        # KPIs (tipo tarjetas) para vendedor seleccionado
        kpi_section = st.container()
        with kpi_section:
            st.subheader("📌 KPIs")
            _kpis_vendedor(df_filtrado, st.session_state.get("vendedor_seleccionado", "Todos"))
            st.caption("Los KPIs reflejan los filtros activos (mes, periodo, producto, método de pago y vendedor).")
        st.divider()

        # Gráficos interactivos (Plotly)
        charts = st.container()
        with charts:
            st.subheader("📊 Análisis")
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
  )        - ✅ Exportación a Excel
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
      