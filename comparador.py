import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
import re
import numpy as np

st.set_page_config(page_title="Comparador de Investigaciones de Mercado", layout="wide")
st.title("📊 Comparador de Investigaciones de Mercado 2026")

def leer_archivo(file):
    """Lee archivo Excel o CSV y asigna nombres de columnas por posición"""
    # Leer el archivo sin encabezados para identificar las columnas
    if file.name.endswith('.csv'):
        # Leer CSV con todas las columnas como texto
        df_raw = pd.read_csv(file, header=None, dtype=str)
    else:
        # Leer Excel con todas las columnas como texto
        df_raw = pd.read_excel(file, header=None, dtype=str)
    
    # Asignar nombres de columnas por posición (según tu estructura)
    # Columna A (0): RFC, Columna B (1): Proveedor, Columna C (2): Clave, 
    # Columna D (3): Descripcion, Columna E (4): Cantidad, 
    # Columna F (5): Pais de origen, Columna G (6): Precio unitario
    columnas = ['RFC', 'PROVEEDOR', 'CLAVE', 'DESCRIPCION', 'CANTIDAD', 'PAIS_ORIGEN', 'PRECIO_UNITARIO']
    
    # Asignar nombres solo a las columnas que existen
    num_columnas = len(df_raw.columns)
    if num_columnas >= 7:
        df_raw.columns = columnas[:num_columnas]
    else:
        # Si tiene menos columnas, ajustar
        df_raw.columns = columnas[:num_columnas] + [f'Columna_{i}' for i in range(num_columnas, 7)]
    
    # Limpiar datos: eliminar filas donde todos los valores sean NaN o vacíos
    df_raw = df_raw.dropna(how='all')
    
    # Si la primera fila contiene encabezados similares, detectar y eliminar
    primera_fila = df_raw.iloc[0].astype(str).str.upper().str.strip()
    encabezados_posibles = ['RFC', 'PROVEEDOR', 'CLAVE', 'DESCRIPCION', 'CANTIDAD', 'PAIS', 'PRECIO']
    
    # Verificar si la primera fila parece ser un encabezado
    coincidencias = sum(1 for val in primera_fila if any(enc in val for enc in encabezados_posibles))
    if coincidencias >= 3:  # Si coincide con al menos 3 encabezados
        # Eliminar la primera fila (es un encabezado)
        df_raw = df_raw.iloc[1:].reset_index(drop=True)
    
    # Limpiar espacios en blanco
    for col in df_raw.columns:
        if df_raw[col].dtype == 'object':
            df_raw[col] = df_raw[col].str.strip()
    
    # Convertir PRECIO_UNITARIO a número (limpiar caracteres especiales)
    if 'PRECIO_UNITARIO' in df_raw.columns:
        # Limpiar $, comas, espacios y convertir a número
        df_raw['PRECIO_UNITARIO'] = df_raw['PRECIO_UNITARIO'].astype(str).str.replace('$', '').str.replace(',', '').str.strip()
        df_raw['PRECIO_UNITARIO'] = pd.to_numeric(df_raw['PRECIO_UNITARIO'], errors='coerce')
    
    # Convertir CANTIDAD a número
    if 'CANTIDAD' in df_raw.columns:
        df_raw['CANTIDAD'] = df_raw['CANTIDAD'].astype(str).str.replace(',', '').str.strip()
        df_raw['CANTIDAD'] = pd.to_numeric(df_raw['CANTIDAD'], errors='coerce')
    
    return df_raw

# Diccionario de mapeo de columnas (para estandarizar nombres después de la lectura)
MAPEO_COLUMNAS = {
    'PROVEEDOR': 'RAZON SOCIAL',
    'PAIS_ORIGEN': 'PAIS DE ORIGEN',
    'PRECIO_UNITARIO': 'PRECIO UNITARIO'
}

def estandarizar_columnas(df):
    """Renombra las columnas al estándar deseado"""
    mapeo = {}
    for col in df.columns:
        col_limpio = col.strip().upper()
        if col_limpio in MAPEO_COLUMNAS:
            mapeo[col] = MAPEO_COLUMNAS[col_limpio]
        elif col_limpio in ['CLAVE']:
            mapeo[col] = 'CLAVE'
        elif col_limpio in ['DESCRIPCION', 'DESCRIPCIÓN']:
            mapeo[col] = 'DESCRIPCION'
    if mapeo:
        df = df.rename(columns=mapeo)
    return df

def limpiar_texto(valor):
    """Convierte cualquier valor a texto limpio"""
    if pd.isna(valor):
        return ''
    return str(valor).strip()

def convertir_todas_columnas_texto(df):
    """Convierte todas las columnas de tipo objeto a texto"""
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].apply(limpiar_texto)
    return df

def unificar_proveedores(df):
    """Unifica proveedores por RFC, usando el nombre más común"""
    if 'RFC' not in df.columns or 'RAZON SOCIAL' not in df.columns:
        return df
    
    # Limpiar RFC (eliminar espacios, convertir a mayúsculas)
    df['RFC'] = df['RFC'].astype(str).str.strip().str.upper()
    df['RAZON SOCIAL'] = df['RAZON SOCIAL'].astype(str).str.strip()
    
    # Eliminar filas donde RFC esté vacío o sea NaN
    df = df[df['RFC'].notna() & (df['RFC'] != '') & (df['RFC'] != 'NAN') & (df['RFC'] != 'nan')]
    
    # Si después de limpiar no hay datos, retornar el DataFrame original
    if df.empty:
        return df
    
    # Crear un mapeo de RFC al nombre más común
    try:
        # Convertir a tipos nativos de Python para evitar problemas
        df['RFC'] = df['RFC'].astype(str)
        df['RAZON SOCIAL'] = df['RAZON SOCIAL'].astype(str)
        
        # Función segura para obtener el valor más común
        def get_most_common(group):
            # Obtener los valores únicos y su frecuencia
            if len(group) == 0:
                return 'N/A'
            
            # Usar value_counts y obtener el índice
            try:
                counts = group.value_counts()
                if len(counts) > 0:
                    # Convertir a lista para evitar problemas de indexación
                    return counts.index.tolist()[0]
                else:
                    return group.iloc[0] if len(group) > 0 else 'N/A'
            except:
                # Si falla, usar el primer valor
                return group.iloc[0] if len(group) > 0 else 'N/A'
        
        # Agrupar y aplicar la función
        rfc_nombre = df.groupby('RFC', as_index=False)['RAZON SOCIAL'].agg(get_most_common)
        
        # Convertir a diccionario
        rfc_nombre_dict = dict(zip(rfc_nombre['RFC'], rfc_nombre['RAZON SOCIAL']))
        
        # Aplicar el mapeo para estandarizar nombres
        df['RAZON SOCIAL'] = df['RFC'].map(rfc_nombre_dict)
        
        # Rellenar valores NaN en RAZON SOCIAL
        df['RAZON SOCIAL'] = df['RAZON SOCIAL'].fillna('N/A')
        
    except Exception as e:
        # Si hay error, mantener los datos sin unificar
        st.warning(f"⚠️ Error al unificar proveedores: {str(e)}")
        pass
    
    return df

# ============================================================
# INTERFAZ DE USUARIO
# ============================================================

uploaded_files = st.file_uploader(
    "Carga tus investigaciones (Excel o CSV)",
    type=["xlsx", "csv"],
    accept_multiple_files=True
)

if uploaded_files:
    all_dfs = []
    nombres_archivos = []
    
    with st.spinner("Cargando y estandarizando archivos..."):
        for file in uploaded_files:
            try:
                # Leer archivo con la nueva función
                df = leer_archivo(file)
                
                # Guardar nombre del archivo
                nombre_archivo = file.name.replace('.xlsx', '').replace('.csv', '')
                nombres_archivos.append(nombre_archivo)
                
                # Aplicar estandarización de columnas
                df = estandarizar_columnas(df)
                
                # Agregar columna con el nombre del archivo
                df['ARCHIVO'] = nombre_archivo
                
                all_dfs.append(df)
                
            except Exception as e:
                st.error(f"❌ Error al procesar el archivo {file.name}: {str(e)}")
                continue
        
        if not all_dfs:
            st.error("❌ No se pudieron procesar los archivos. Verifica el formato.")
            st.stop()
        
        df_combined = pd.concat(all_dfs, ignore_index=True)
        
        # Convertir todas las columnas a texto
        df_combined = convertir_todas_columnas_texto(df_combined)
        
        # UNIFICAR PROVEEDORES POR RFC
        df_combined = unificar_proveedores(df_combined)
        
        # Convertir PRECIO UNITARIO a número (si no se hizo en la lectura)
        if 'PRECIO UNITARIO' in df_combined.columns:
            df_combined['PRECIO UNITARIO'] = pd.to_numeric(df_combined['PRECIO UNITARIO'], errors='coerce')
        
        # Convertir CANTIDAD OFERTADA a número
        if 'CANTIDAD OFERTADA' in df_combined.columns:
            df_combined['CANTIDAD OFERTADA'] = pd.to_numeric(df_combined['CANTIDAD OFERTADA'], errors='coerce')
    
    # Mostrar información de depuración
    with st.expander("🔍 Información de depuración - Verificar columnas"):
        st.write("**Columnas detectadas en los archivos:**")
        st.write(df_combined.columns.tolist())
        st.write("**Primeras 5 filas de datos:**")
        st.dataframe(df_combined.head(5))
        st.write("**Tipos de datos:**")
        st.write(df_combined.dtypes)
    
    st.success(f"✅ Datos cargados: {len(df_combined)} registros de {len(uploaded_files)} investigaciones")
    
    # Mostrar archivos cargados
    with st.expander("📁 Archivos cargados"):
        for i, nombre in enumerate(nombres_archivos, 1):
            st.write(f"{i}. {nombre}")
    
    # ============================================================
    # BLOQUE 1: RESUMEN TOTAL
    # ============================================================
    st.header("📊 RESUMEN TOTAL")
    st.markdown("**Estadísticas generales de todas las investigaciones cargadas**")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📌 Total de Claves Únicas", df_combined['CLAVE'].nunique() if 'CLAVE' in df_combined.columns else 0)
    with col2:
        st.metric("📁 Total de Investigaciones", len(nombres_archivos))
    with col3:
        proveedores_unicos = df_combined['RAZON SOCIAL'].nunique() if 'RAZON SOCIAL' in df_combined.columns else 0
        st.metric("🏢 Total de Proveedores", proveedores_unicos)
    
    # Mostrar lista de investigaciones
    with st.expander("📋 Lista de investigaciones cargadas"):
        for i, nombre in enumerate(nombres_archivos, 1):
            st.write(f"{i}. {nombre}")
    
    # ============================================================
    # BLOQUE 2: ANÁLISIS POR CLAVE
    # ============================================================
    st.header("🔍 ANÁLISIS POR CLAVE")
    st.markdown("**Selecciona una clave para ver el detalle completo**")
    
    # Verificar que exista la columna CLAVE
    if 'CLAVE' not in df_combined.columns:
        st.error("❌ No se encontró la columna 'CLAVE'")
        st.write("Columnas disponibles:", df_combined.columns.tolist())
        st.stop()
    
    # Obtener claves únicas y ordenarlas
    claves_unicas = sorted(df_combined['CLAVE'].unique())
    claves_unicas = [c for c in claves_unicas if c and str(c).strip() != '' and str(c).strip() != 'NAN' and str(c).strip() != 'nan']
    
    if len(claves_unicas) == 0:
        st.warning("⚠️ No se encontraron CLAVES válidas")
        st.stop()
    
    clave_seleccionada = st.selectbox("Selecciona una CLAVE para análisis detallado", claves_unicas, key="clave_selector")
    
    # Variable global para usar en otros bloques
    df_clave_filtrado = None
    
    if clave_seleccionada:
        # Filtrar datos de la clave seleccionada
        df_clave = df_combined[df_combined['CLAVE'] == clave_seleccionada].copy()
        df_clave = df_clave.dropna(subset=['PRECIO UNITARIO'])
        df_clave_filtrado = df_clave  # Guardar para usar en otros bloques
        
        if len(df_clave) > 0:
            st.subheader(f"📌 Análisis de la clave: {clave_seleccionada}")
            
            # Mostrar descripción si existe
            if 'DESCRIPCION' in df_clave.columns and not df_clave['DESCRIPCION'].isna().all():
                descripcion = df_clave['DESCRIPCION'].iloc[0]
                st.info(f"📝 **Descripción:** {descripcion}")
            
            # Tabla: Archivo, Precio Máximo, Precio Mínimo, Proveedores
            st.subheader("📋 Detalle por archivo")
            
            detalle_archivos = []
            for archivo in sorted(df_clave['ARCHIVO'].unique()):
                df_archivo = df_clave[df_clave['ARCHIVO'] == archivo]
                
                # Precios
                precio_min = df_archivo['PRECIO UNITARIO'].min()
                precio_max = df_archivo['PRECIO UNITARIO'].max()
                
                # Proveedores con sus precios
                proveedores_list = []
                for _, row in df_archivo.iterrows():
                    proveedor = row.get('RAZON SOCIAL', 'N/A')
                    precio = row.get('PRECIO UNITARIO', 'N/A')
                    if precio != 'N/A' and pd.notna(precio):
                        proveedores_list.append(f"{proveedor}: ${precio:,.2f}")
                
                detalle_archivos.append({
                    'ARCHIVO': archivo,
                    'PRECIO MÍNIMO': f"${precio_min:,.2f}",
                    'PRECIO MÁXIMO': f"${precio_max:,.2f}",
                    'PROVEEDORES Y PRECIOS': ', '.join(proveedores_list)
                })
            
            df_detalle = pd.DataFrame(detalle_archivos)
            st.dataframe(df_detalle, use_container_width=True, hide_index=True)
            
            # Mostrar proveedores repetidos entre archivos
            st.subheader("🔄 Proveedores que aparecen en múltiples investigaciones")
            
            # Encontrar proveedores que aparecen en más de un archivo
            todos_proveedores = df_clave['RAZON SOCIAL'].unique()
            proveedores_repetidos = {}
            
            for proveedor in todos_proveedores:
                archivos_proveedor = df_clave[df_clave['RAZON SOCIAL'] == proveedor]
                archivos_unicos = archivos_proveedor['ARCHIVO'].unique()
                
                if len(archivos_unicos) > 1:
                    precios = []
                    for archivo in archivos_unicos:
                        precio = archivos_proveedor[archivos_proveedor['ARCHIVO'] == archivo]['PRECIO UNITARIO'].iloc[0]
                        precios.append({'archivo': archivo, 'precio': precio})
                    proveedores_repetidos[proveedor] = precios
            
            if proveedores_repetidos:
                for proveedor, archivos in proveedores_repetidos.items():
                    st.markdown(f"**{proveedor}**")
                    for item in archivos:
                        st.write(f"  • {item['archivo']}: ${item['precio']:,.2f}")
                    
                    # Calcular variación
                    precios = [item['precio'] for item in archivos]
                    if len(precios) > 1:
                        precio_min = min(precios)
                        precio_max = max(precios)
                        variacion = ((precio_max - precio_min) / precio_min) * 100
                        st.write(f"  📊 **Variación:** ${precio_min:,.2f} - ${precio_max:,.2f} ({variacion:.1f}% de diferencia)")
                    st.write("")
            else:
                st.info("✅ No hay proveedores repetidos entre investigaciones para esta clave")
            
            # Tabla pivot: Archivo vs Proveedor
            with st.expander("📊 Ver tabla comparativa (Archivo vs Proveedor)"):
                pivot_table = df_clave.pivot_table(
                    values='PRECIO UNITARIO',
                    index='ARCHIVO',
                    columns='RAZON SOCIAL',
                    aggfunc='first'
                ).round(2)
                st.dataframe(pivot_table, use_container_width=True)
        
        else:
            st.warning(f"⚠️ No hay datos con precios válidos para la CLAVE {clave_seleccionada}")
    
    # ============================================================
    # BLOQUE 3: DETALLE COMPLETO DE CADA INVESTIGACIÓN (FILTRADO POR CLAVE)
    # ============================================================
    st.header("📁 DETALLE COMPLETO DE CADA INVESTIGACIÓN")
    st.markdown(f"**Detalle de la clave {clave_seleccionada if clave_seleccionada else 'seleccionada'} en cada investigación**")
    
    if clave_seleccionada and df_clave_filtrado is not None and len(df_clave_filtrado) > 0:
        # Mostrar el detalle por cada archivo para la clave seleccionada
        st.subheader(f"📋 Detalle de {clave_seleccionada} por investigación")
        
        # Crear tabs para cada archivo
        archivos_clave = sorted(df_clave_filtrado['ARCHIVO'].unique())
        tabs = st.tabs([f"📁 {archivo}" for archivo in archivos_clave])
        
        for i, archivo in enumerate(archivos_clave):
            with tabs[i]:
                df_archivo = df_clave_filtrado[df_clave_filtrado['ARCHIVO'] == archivo]
                
                # Métricas del archivo
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total de proveedores", len(df_archivo))
                with col2:
                    st.metric("Precio mínimo", f"${df_archivo['PRECIO UNITARIO'].min():,.2f}")
                with col3:
                    st.metric("Precio máximo", f"${df_archivo['PRECIO UNITARIO'].max():,.2f}")
                
                # Mostrar datos completos
                columnas_mostrar = ['RFC', 'RAZON SOCIAL', 'DESCRIPCION', 'PRECIO UNITARIO', 'PAIS DE ORIGEN', 'CANTIDAD OFERTADA']
                columnas_existentes = [col for col in columnas_mostrar if col in df_archivo.columns]
                st.dataframe(df_archivo[columnas_existentes], use_container_width=True, hide_index=True)
                
                # Mostrar proveedor con mejor precio
                mejor_proveedor = df_archivo.loc[df_archivo['PRECIO UNITARIO'].idxmin()]
                st.success(f"🏆 **Mejor precio en {archivo}:** {mejor_proveedor['RAZON SOCIAL']} con ${mejor_proveedor['PRECIO UNITARIO']:,.2f}")
    else:
        if not clave_seleccionada:
            st.info("👆 Primero selecciona una clave en el Bloque 2")
        else:
            st.warning(f"⚠️ No hay datos para la clave {clave_seleccionada}")
    
    # ============================================================
    # BLOQUE 4: GRÁFICAS COMPARATIVAS
    # ============================================================
    st.header("📈 GRÁFICAS COMPARATIVAS")
    st.markdown("**Visualización de precios por investigación y proveedor**")
    
    if clave_seleccionada and df_clave_filtrado is not None and len(df_clave_filtrado) > 0:
        df_clave_graf = df_clave_filtrado
        
        # Gráfica 1: Barras agrupadas por archivo con proveedores
        st.subheader(f"📊 Precios por investigación - {clave_seleccionada}")
        
        fig1 = px.bar(
            df_clave_graf,
            x='ARCHIVO',
            y='PRECIO UNITARIO',
            color='RAZON SOCIAL',
            text='PRECIO UNITARIO',
            title=f"Precios por investigación - {clave_seleccionada}",
            labels={"PRECIO UNITARIO": "Precio ($)", "ARCHIVO": "Investigación", "RAZON SOCIAL": "Proveedor"},
            barmode='group'
        )
        fig1.update_traces(texttemplate='$%{text:.2f}', textposition='outside')
        fig1.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig1, use_container_width=True)
        
        # Gráfica 2: Precio más bajo por investigación con nombre del proveedor
        st.subheader(f"🏆 Precio más bajo por investigación - {clave_seleccionada}")
        
        # Encontrar el proveedor con el precio más bajo por archivo
        min_por_archivo = []
        for archivo in sorted(df_clave_graf['ARCHIVO'].unique()):
            df_archivo = df_clave_graf[df_clave_graf['ARCHIVO'] == archivo]
            idx_min = df_archivo['PRECIO UNITARIO'].idxmin()
            row_min = df_archivo.loc[idx_min]
            min_por_archivo.append({
                'ARCHIVO': archivo,
                'PROVEEDOR': row_min['RAZON SOCIAL'],
                'PRECIO MÍNIMO': row_min['PRECIO UNITARIO']
            })
        
        df_min = pd.DataFrame(min_por_archivo)
        
        fig2 = px.bar(
            df_min,
            x='ARCHIVO',
            y='PRECIO MÍNIMO',
            text='PRECIO MÍNIMO',
            color='PROVEEDOR',
            title=f"Precio más bajo por investigación - {clave_seleccionada}",
            labels={"PRECIO MÍNIMO": "Precio mínimo ($)", "ARCHIVO": "Investigación", "PROVEEDOR": "Proveedor"},
            hover_data={'PROVEEDOR': True}
        )
        fig2.update_traces(texttemplate='$%{text:.2f}', textposition='outside')
        fig2.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig2, use_container_width=True)
    else:
        if not clave_seleccionada:
            st.info("👆 Primero selecciona una clave en el Bloque 2 para generar las gráficas")
        else:
            st.warning(f"⚠️ No hay datos con precios válidos para la CLAVE {clave_seleccionada}")
    
    # ============================================================
    # BLOQUE 5: RESUMEN POR INVESTIGACIÓN (SIN PRECIOS)
    # ============================================================
    st.header("📊 RESUMEN POR INVESTIGACIÓN")
    st.markdown("**Estadísticas generales de cada investigación (sin precios)**")
    
    if 'ARCHIVO' in df_combined.columns:
        resumen_sin_precios = df_combined.groupby('ARCHIVO').agg({
            'CLAVE': 'nunique',
            'RAZON SOCIAL': 'nunique',
            'RFC': 'nunique'
        }).reset_index()
        resumen_sin_precios.columns = ['Investigación', 'Total Claves', 'Total Proveedores', 'Total RFCs']
        
        # Ordenar por total de claves
        resumen_sin_precios = resumen_sin_precios.sort_values('Total Claves', ascending=False)
        
        st.dataframe(resumen_sin_precios, use_container_width=True, hide_index=True)
        
        # Gráfica de resumen
        # fig3 = px.bar(
        #     resumen_sin_precios,
        #     x='Investigación',
        #     y='Total Claves',
        #     text='Total Claves',
        #     title="Número de claves por investigación",
        #     labels={"Total Claves": "Cantidad de claves", "Investigación": "Investigación"},
        #     color='Total Claves',
        #     color_continuous_scale='Viridis'
        # )
        # fig3.update_traces(textposition='outside')
        # st.plotly_chart(fig3, use_container_width=True)
       
    # ============================================================
    # BLOQUE 6: ANÁLISIS DETALLADO DE PROVEEDORES
    # ============================================================
    st.header("🏢 BLOQUE 7: ANÁLISIS DETALLADO DE PROVEEDORES")
    st.markdown("**Desglose completo de cada proveedor: investigaciones, claves, precios, países de origen y análisis de variaciones**")

    if 'RAZON SOCIAL' in df_combined.columns and 'RFC' in df_combined.columns:
        # Obtener lista de proveedores únicos
        proveedores_unicos = sorted(df_combined['RAZON SOCIAL'].unique())
        proveedores_unicos = [p for p in proveedores_unicos if p and str(p).strip() != '' and str(p).strip() != 'NAN' and str(p).strip() != 'nan']
        
        if len(proveedores_unicos) > 0:
            # Selector de proveedor
            proveedor_seleccionado = st.selectbox(
                "Selecciona un proveedor para análisis detallado",
                proveedores_unicos,
                key="proveedor_selector"
            )
            
            if proveedor_seleccionado:
                # Filtrar datos del proveedor seleccionado
                df_proveedor = df_combined[df_combined['RAZON SOCIAL'] == proveedor_seleccionado].copy()
                
                # ============================================================
                # FUNCIÓN PARA EXTRAER NÚMERO DE INVESTIGACIÓN Y ORDENAR
                # ============================================================
                def extraer_numero_investigacion(nombre_archivo):
                    """Extrae el número de investigación del nombre del archivo"""
                    try:
                        # Buscar patrón IM-XXX o IM-XXXX
                        import re
                        match = re.search(r'IM-(\d+)', str(nombre_archivo))
                        if match:
                            return int(match.group(1))
                        else:
                            # Si no encuentra IM-, buscar cualquier número
                            match = re.search(r'(\d+)', str(nombre_archivo))
                            if match:
                                return int(match.group(1))
                            else:
                                return 999  # Valor alto para archivos sin número
                    except:
                        return 999
                
                # Agregar columna con número de investigación para ordenar
                df_proveedor['NUM_INVESTIGACION'] = df_proveedor['ARCHIVO'].apply(extraer_numero_investigacion)
                
                # Ordenar todo el dataframe por número de investigación
                df_proveedor = df_proveedor.sort_values('NUM_INVESTIGACION')
                
                # Métricas del proveedor
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    rfc_proveedor = df_proveedor['RFC'].iloc[0] if len(df_proveedor) > 0 else 'N/A'
                    st.metric("📋 RFC", rfc_proveedor)
                with col2:
                    st.metric("📌 Claves distintas", df_proveedor['CLAVE'].nunique())
                with col3:
                    st.metric("📁 Investigaciones", df_proveedor['ARCHIVO'].nunique())
                with col4:
                    st.metric("💰 Precio promedio", f"${df_proveedor['PRECIO UNITARIO'].mean():,.2f}")
                
                st.subheader(f"📋 Detalle completo de {proveedor_seleccionado}")
                
                # Mostrar todas las participaciones del proveedor (ordenado por número de investigación)
                columnas_mostrar_prov = ['CLAVE', 'ARCHIVO', 'DESCRIPCION', 'PRECIO UNITARIO', 'PAIS DE ORIGEN', 'CANTIDAD OFERTADA']
                columnas_existentes_prov = [col for col in columnas_mostrar_prov if col in df_proveedor.columns]
                
                # Ordenar por número de investigación y luego por clave
                df_proveedor_mostrar = df_proveedor.sort_values(['NUM_INVESTIGACION', 'CLAVE'])[columnas_existentes_prov]
                st.dataframe(df_proveedor_mostrar, use_container_width=True, hide_index=True)
                
                # ============================================================
                # ANÁLISIS DE VARIACIONES POR CLAVE (SOLO CLAVES REPETIDAS)
                # ============================================================
                st.subheader("📊 Análisis de variaciones por clave (claves con múltiples investigaciones)")
                
                # Identificar claves que aparecen en múltiples investigaciones
                claves_conteo = df_proveedor.groupby('CLAVE')['ARCHIVO'].nunique()
                claves_repetidas = claves_conteo[claves_conteo > 1].index.tolist()
                
                if claves_repetidas:
                    st.info(f"🔍 Se encontraron {len(claves_repetidas)} claves con participación en múltiples investigaciones")
                    
                    for clave in sorted(claves_repetidas):
                        df_clave_prov = df_proveedor[df_proveedor['CLAVE'] == clave].copy()
                        
                        # Ordenar por número de investigación
                        df_clave_prov = df_clave_prov.sort_values('NUM_INVESTIGACION')
                        
                        st.markdown(f"**🔑 Clave: {clave}**")
                        
                        # Mostrar descripción si existe
                        if 'DESCRIPCION' in df_clave_prov.columns and not df_clave_prov['DESCRIPCION'].isna().all():
                            desc = df_clave_prov['DESCRIPCION'].iloc[0]
                            st.info(f"📝 {desc}")
                        
                        # Crear tabla de precios por investigación (ordenada cronológicamente)
                        datos_variacion = []
                        for _, row in df_clave_prov.iterrows():
                            datos_variacion.append({
                                'Investigación': row['ARCHIVO'],
                                'Número': row['NUM_INVESTIGACION'],
                                'Precio': row['PRECIO UNITARIO'],
                                'País de origen': row.get('PAIS DE ORIGEN', 'N/A'),
                                'Cantidad': row.get('CANTIDAD OFERTADA', 'N/A')
                            })
                        
                        df_variacion = pd.DataFrame(datos_variacion)
                        
                        # Ordenar explícitamente por número de investigación
                        df_variacion = df_variacion.sort_values('Número')
                        
                        # Calcular variaciones
                        if len(df_variacion) > 1:
                            # Guardar el orden original para la gráfica
                            orden_investigaciones = df_variacion['Investigación'].tolist()
                            
                            # Calcular diferencias en el orden cronológico
                            df_variacion['Diferencia vs anterior'] = df_variacion['Precio'].diff()
                            df_variacion['% variación'] = df_variacion['Precio'].pct_change() * 100
                            
                            # Identificar el precio más bajo y más alto
                            precio_min = df_variacion['Precio'].min()
                            precio_max = df_variacion['Precio'].max()
                            variacion_total = ((precio_max - precio_min) / precio_min) * 100 if precio_min > 0 else 0
                            
                            # Mostrar resumen
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("💰 Precio más bajo", f"${precio_min:,.2f}")
                            with col2:
                                st.metric("💰 Precio más alto", f"${precio_max:,.2f}")
                            with col3:
                                # Mostrar tendencia con flecha
                                precio_inicial = df_variacion.iloc[0]['Precio']
                                precio_final = df_variacion.iloc[-1]['Precio']
                                cambio_total = ((precio_final - precio_inicial) / precio_inicial) * 100 if precio_inicial > 0 else 0
                                flecha = "📈" if cambio_total > 0 else "📉" if cambio_total < 0 else "➡️"
                                st.metric("📊 Variación total", f"{flecha} {cambio_total:.1f}%")
                            
                            # Mostrar tabla detallada con formato (en orden cronológico)
                            df_variacion_formateada = df_variacion.copy()
                            df_variacion_formateada['Precio'] = df_variacion_formateada['Precio'].apply(lambda x: f"${x:,.2f}")
                            df_variacion_formateada['Diferencia vs anterior'] = df_variacion_formateada['Diferencia vs anterior'].apply(
                                lambda x: f"+${x:,.2f}" if pd.notna(x) and x > 0 else f"${x:,.2f}" if pd.notna(x) else ""
                            )
                            df_variacion_formateada['% variación'] = df_variacion_formateada['% variación'].apply(
                                lambda x: f"+{x:.1f}%" if pd.notna(x) and x > 0 else f"{x:.1f}%" if pd.notna(x) else ""
                            )
                            
                            # Mostrar tabla (solo columnas relevantes)
                            columnas_tabla = ['Investigación', 'Precio', 'Diferencia vs anterior', '% variación', 'País de origen']
                            st.dataframe(df_variacion_formateada[columnas_tabla], use_container_width=True, hide_index=True)
                            
                            # Análisis de país de origen
                            paises = df_clave_prov['PAIS DE ORIGEN'].unique()
                            if len(paises) > 1 and 'PAIS DE ORIGEN' in df_clave_prov.columns:
                                st.markdown("**🌍 Cambios en país de origen:**")
                                for _, row in df_clave_prov.iterrows():
                                    st.write(f"  • {row['ARCHIVO']}: {row['PAIS DE ORIGEN']}")
                            
                            # ============================================================
                            # GRÁFICA DE EVOLUCIÓN DE PRECIOS (ORDENADA CRONOLÓGICAMENTE)
                            # ============================================================
                            # Asegurarse de que los datos estén en el orden correcto
                            df_grafica = df_variacion.copy()
                            df_grafica['Investigación'] = pd.Categorical(
                                df_grafica['Investigación'], 
                                categories=orden_investigaciones, 
                                ordered=True
                            )
                            df_grafica = df_grafica.sort_values('Investigación')
                            
                            fig_prov = px.line(
                                df_grafica,
                                x='Investigación',
                                y='Precio',
                                markers=True,
                                text='Precio',
                                title=f"Evolución de precios para {proveedor_seleccionado} - Clave {clave}",
                                labels={"Precio": "Precio ($)", "Investigación": "Investigación"},
                                line_shape='linear'
                            )
                            
                            # Personalizar la gráfica
                            fig_prov.update_traces(
                                texttemplate='$%{y:.2f}', 
                                textposition='top center',
                                marker=dict(size=12),
                                line=dict(width=3)
                            )
                            
                            # Añadir área sombreada para mejor visualización
                            fig_prov.update_layout(
                                xaxis_title="Investigación (Orden cronológico)",
                                yaxis_title="Precio ($)",
                                hovermode='x unified',
                                plot_bgcolor='rgba(0,0,0,0)',
                                paper_bgcolor='rgba(0,0,0,0)',
                                xaxis=dict(
                                    tickangle=45,
                                    showgrid=True,
                                    gridcolor='rgba(128,128,128,0.2)'
                                ),
                                yaxis=dict(
                                    showgrid=True,
                                    gridcolor='rgba(128,128,128,0.2)',
                                    zeroline=True,
                                    zerolinecolor='rgba(128,128,128,0.2)'
                                )
                            )
                            
                            # Si hay al menos 2 puntos, mostrar en gráfica
                            st.plotly_chart(fig_prov, use_container_width=True)
                            
                            # ============================================================
                            # ANÁLISIS DE TENDENCIA
                            # ============================================================
                            precios = df_variacion['Precio'].values
                            investigaciones = df_variacion['Investigación'].tolist()
                            
                            if len(precios) >= 2:
                                precio_inicial = precios[0]
                                precio_final = precios[-1]
                                cambio_total = ((precio_final - precio_inicial) / precio_inicial) * 100 if precio_inicial > 0 else 0
                                
                                # Determinar tendencia
                                if cambio_total > 5:
                                    tendencia = "📈 Aumento significativo"
                                    color = "red"
                                elif cambio_total > 0:
                                    tendencia = "📈 Aumento leve"
                                    color = "orange"
                                elif cambio_total < -5:
                                    tendencia = "📉 Disminución significativa"
                                    color = "green"
                                elif cambio_total < 0:
                                    tendencia = "📉 Disminución leve"
                                    color = "lightgreen"
                                else:
                                    tendencia = "➡️ Estable"
                                    color = "blue"
                                
                                # Mostrar análisis detallado
                                st.markdown(f"**📊 Análisis de tendencia:**")
                                st.markdown(f"• **Tendencia general:** {tendencia}")
                                st.markdown(f"• **Cambio total:** {cambio_total:+.1f}% (de ${precio_inicial:,.2f} a ${precio_final:,.2f})")
                                
                                # Mostrar pasos intermedios
                                if len(precios) > 2:
                                    st.markdown(f"• **Número de investigaciones analizadas:** {len(precios)}")
                                    cambios_intermedios = []
                                    for i in range(1, len(precios)):
                                        cambio = ((precios[i] - precios[i-1]) / precios[i-1]) * 100 if precios[i-1] > 0 else 0
                                        cambios_intermedios.append(f"{investigaciones[i-1]} → {investigaciones[i]}: {cambio:+.1f}%")
                                    st.markdown("• **Cambios intermedios:**")
                                    for cambio in cambios_intermedios:
                                        st.markdown(f"  - {cambio}")
                        
                    else:
                        st.info("ℹ️ Este proveedor no tiene claves que se repitan en múltiples investigaciones. Todas sus claves son únicas por investigación.")
                        st.write("Las claves únicas se muestran en la tabla de detalle completo anterior.")
                
                # ============================================================
                # RESUMEN GENERAL DEL PROVEEDOR
                # ============================================================
                st.subheader("📊 Resumen general del proveedor")
                
                # Función segura para unir países
                def join_paises(x):
                    try:
                        valores = x.astype(str).str.strip()
                        valores = valores[valores != '']
                        valores = valores[valores != 'nan']
                        valores = valores[valores != 'NAN']
                        valores = valores[valores != 'None']
                        if len(valores) > 0:
                            return ', '.join(sorted(valores.unique()))
                        else:
                            return 'N/A'
                    except:
                        return 'N/A'
                
                # Función segura para unir archivos
                def join_archivos(x):
                    try:
                        valores = x.astype(str).str.strip()
                        valores = valores[valores != '']
                        if len(valores) > 0:
                            return ', '.join(sorted(valores.unique()))
                        else:
                            return 'N/A'
                    except:
                        return 'N/A'
                
                try:
                    # Crear resumen por clave
                    resumen_proveedor = df_proveedor.groupby('CLAVE').agg({
                        'ARCHIVO': join_archivos,
                        'PRECIO UNITARIO': ['min', 'max', 'mean', 'count'],
                        'PAIS DE ORIGEN': join_paises
                    }).reset_index()
                    
                    resumen_proveedor.columns = ['CLAVE', 'INVESTIGACIONES', 'PRECIO_MIN', 'PRECIO_MAX', 'PRECIO_PROM', 'TOTAL_REGISTROS', 'PAISES']
                    
                    # Formatear precios
                    resumen_proveedor['PRECIO_MIN'] = resumen_proveedor['PRECIO_MIN'].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else 'N/A')
                    resumen_proveedor['PRECIO_MAX'] = resumen_proveedor['PRECIO_MAX'].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else 'N/A')
                    resumen_proveedor['PRECIO_PROM'] = resumen_proveedor['PRECIO_PROM'].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else 'N/A')
                    
                    st.dataframe(resumen_proveedor, use_container_width=True, hide_index=True)
                    
                except Exception as e:
                    st.warning(f"⚠️ Error al generar el resumen del proveedor: {str(e)}")
                    
        else:
            st.warning("⚠️ No se encontraron proveedores válidos en los datos")
    else:
        st.warning("⚠️ No se encontraron las columnas necesarias para el análisis de proveedores")
    
    # ============================================================
    # BLOQUE 7: DESCARGA DE ARCHIVO EXCEL
    # ============================================================
    st.header("📥 DESCARGA DE ARCHIVO EXCEL")
    st.markdown("**Exporta toda la información procesada a un archivo Excel**")
    
    # Crear un Excel con todas las hojas
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Hoja 1: Datos completos
        df_combined.to_excel(writer, sheet_name="Datos completos", index=False)
        
        # Hoja 2: Resumen de claves
        if 'CLAVE' in df_combined.columns:
            resumen_claves = df_combined.groupby('CLAVE').agg({
                'ARCHIVO': lambda x: ', '.join(x.unique()),
                'RAZON SOCIAL': lambda x: ', '.join(x.unique()),
                'PRECIO UNITARIO': ['min', 'max', 'mean', 'count'],
                'DESCRIPCION': 'first'
            }).reset_index()
            resumen_claves.columns = ['CLAVE', 'ARCHIVOS', 'PROVEEDORES', 'PRECIO_MIN', 'PRECIO_MAX', 'PRECIO_PROM', 'TOTAL_REGISTROS', 'DESCRIPCION']
            resumen_claves.to_excel(writer, sheet_name="Resumen por clave", index=False)
        
        # Hoja 3: Resumen por archivo
        if 'ARCHIVO' in df_combined.columns:
            resumen_archivo = df_combined.groupby('ARCHIVO').agg({
                'CLAVE': 'nunique',
                'RAZON SOCIAL': 'nunique',
                'RFC': 'nunique'
            }).reset_index()
            resumen_archivo.columns = ['Investigación', 'Total Claves', 'Total Proveedores', 'Total RFCs']
            resumen_archivo.to_excel(writer, sheet_name="Resumen por archivo", index=False)
        
        # Hoja 4: Lista de proveedores unificados
        if 'RFC' in df_combined.columns and 'RAZON SOCIAL' in df_combined.columns:
            proveedores_unificados = df_combined[['RFC', 'RAZON SOCIAL']].drop_duplicates().sort_values('RAZON SOCIAL')
            proveedores_unificados.to_excel(writer, sheet_name="Proveedores unificados", index=False)
        
        # Hoja 5: Detalle de la clave seleccionada (si existe)
        if clave_seleccionada and df_clave_filtrado is not None and len(df_clave_filtrado) > 0:
            df_clave_filtrado.to_excel(writer, sheet_name=f"Detalle_{clave_seleccionada}", index=False)
    
    st.download_button(
        label="📥 Descargar análisis completo en Excel",
        data=output.getvalue(),
        file_name="analisis_completo_investigaciones.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    st.success("✅ El archivo Excel contiene: Datos completos, Resumen por clave, Resumen por archivo, Proveedores unificados y Detalle de la clave seleccionada")

    
else:
    st.info("👆 Carga al menos un archivo para comenzar")