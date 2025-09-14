
import pandas as pd
import re
import plotly.express as px
import plotly.io as pio
import requests
pio.renderers.default = "browser"  # força abrir no navegador


def extract_area(desc):
    desc_lower = desc.lower()
    # Procurar "x de área privativa"
    priv = re.search(r'([\d,.]+) de área privativa', desc)
    
    # Procurar "x de área do terreno"
    terreno = re.search(r'([\d,.]+) de área do terreno', desc)
    
    # Converter para float, trocando vírgula por ponto; se não achar, usa 0
    priv_value = float(priv.group(1).replace(',', '.')) if priv else 0
    terreno_value = float(terreno.group(1).replace(',', '.')) if terreno else 0
    
    # identificar o tipo de imóvel
    if 'casa' in desc_lower:
        tipo = 'Casa'
    elif 'apartamento' in desc_lower or 'apto' in desc_lower:
        tipo = ' Apartamento'
    elif 'loja' in desc_lower:
        tipo = 'Loja'
    elif 'comercial' in desc_lower:
        tipo = 'Comercial'
    elif 'terreno' in desc_lower:
        tipo = 'Terreno'
    else:
        tipo = 'outro'
    return priv_value , terreno_value , tipo  
 
def agrupar_tipo(tipo):
    if tipo in ['Casa','Apartamento','Loja', 'Comercial']:
        return 'Construção'
    elif tipo == 'Terreno':
        return 'Terreno'
    else:
        return 'Outro'

def calcular_preco_m2(row):
    if row['Tipo_agrupado'] == 'Construção':
        return row['Preço'] / row['Área_privativa'] if row['Área_privativa'] > 0 else 0
    elif row['Tipo_agrupado'] == 'Terreno':
        return row['Preço'] / row['Área_terreno'] if row['Área_terreno'] > 0 else 0
    else:
        return 0

def calcular_preco_medio(df, grupo_col='UF', limite_max=50000, usar_quantis=True):
    """
    Calcula o preço médio por m² por grupo, removendo nulos e outliers.
    
    Parâmetros:
    df : DataFrame original
    grupo_col : coluna para agrupar ('UF', 'Cidade', 'Bairro', etc.)
    limite_max : valor máximo aceitável de Preco_por_m2
    usar_quantis : se True, remove os 1% mais baixos e 1% mais altos
    
    Retorna:
    DataFrame com coluna Preco_medio_m2 por grupo
    """
    
    # Remover nulos
    df_filtrado = df.dropna(subset=['Preco_por_m2'])
    
    # Remover outliers acima do limite máximo
    df_filtrado = df_filtrado[df_filtrado['Preco_por_m2'] <= limite_max]
    
    # Remover outliers pelos quantis
    if usar_quantis:
        q_low = df_filtrado['Preco_por_m2'].quantile(0.01)
        q_high = df_filtrado['Preco_por_m2'].quantile(0.99)
        df_filtrado = df_filtrado[(df_filtrado['Preco_por_m2'] >= q_low) &
                                  (df_filtrado['Preco_por_m2'] <= q_high)]
    
    # Agrupar e calcular média
    preco_medio = df_filtrado.groupby([grupo_col, 'Tipo_agrupado'])['Preco_por_m2'].mean().reset_index()
    preco_medio.rename(columns={'Preco_por_m2':'Preco_medio_m2'}, inplace=True)
    
    return preco_medio


df = pd.read_csv("Lista_imoveis_geral.csv",sep =";" ,encoding="latin1", header = 1)

money_cols = ['Preço', 'Valor de avaliação']
for col in money_cols:
    df[col] = df[col].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
    df[col] = pd.to_numeric(df[col], errors='coerce')
    
# o código acima serve para limpar as colunas e fazer de tal forma que o python
# consiga entender e trabalhar com os valores.

df[['Área_privativa','Área_terreno','Tipo']] = pd.DataFrame(
    df['Descrição'].apply(extract_area).tolist(),
    index=df.index
)



df['Tipo_agrupado'] = df['Tipo'].apply(agrupar_tipo)



df['Preco_por_m2'] = df.apply(calcular_preco_m2, axis=1)

# Preço médio por estado
preco_estado = calcular_preco_medio(df, grupo_col='UF')

# Preço médio por cidade
preco_cidade = calcular_preco_medio(df, grupo_col='Cidade')

# Preço médio por bairro de São Paulo
df_sp = df[df['Cidade'] == 'São Paulo']
preco_bairro = calcular_preco_medio(df_sp, grupo_col='Bairro')

url = 'https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson'
geojson = requests.get(url).json()

# Supondo que preco_estado já existe e tenha colunas UF e Preco_medio_m2
# Se necessário, garantir que UF seja maiúsculo e sem espaços
preco_estado['UF'] = preco_estado['UF'].str.upper().str.strip()

# Mapeamento UF → Nome completo
uf_to_name = {
    "AC":"Acre", "AL":"Alagoas", "AP":"Amapá", "AM":"Amazonas", "BA":"Bahia",
    "CE":"Ceará", "DF":"Distrito Federal", "ES":"Espírito Santo", "GO":"Goiás",
    "MA":"Maranhão", "MT":"Mato Grosso", "MS":"Mato Grosso do Sul", "MG":"Minas Gerais",
    "PA":"Pará", "PB":"Paraíba", "PR":"Paraná", "PE":"Pernambuco", "PI":"Piauí",
    "RJ":"Rio de Janeiro", "RN":"Rio Grande do Norte", "RS":"Rio Grande do Sul",
    "RO":"Rondônia", "RR":"Roraima", "SC":"Santa Catarina", "SP":"São Paulo",
    "SE":"Sergipe", "TO":"Tocantins"
}

# Criar coluna com o nome completo
preco_estado['Estado'] = preco_estado['UF'].map(uf_to_name)

fig_map = px.choropleth(
    preco_estado,
    geojson=geojson,
    locations='UF',
    featureidkey="properties.sigla",
    color='Preco_medio_m2',
    color_continuous_scale='Plasma',
    title='Preço médio por m² por Estado'
)

# adicionar customdata para hover
fig_map.update_traces(
    marker_line_width=1,
    marker_line_color="white",
    hovertemplate="<b>%{location} - %{customdata[0]}</b><br>Preço médio: R$ %{z:,.2f}/m²<extra></extra>",
    customdata=preco_estado[['Estado']].values
)

# Ajustar visual
fig_map.update_geos(fitbounds="locations", visible=False)

fig_map.update_traces(
    marker_line_width=1,
    marker_line_color="white",
    hovertemplate="<b>%{location} - %{customdata[0]}</b><br>Preço médio: R$ %{z:,.2f}/m²<extra></extra>"
)

fig_map.update_layout(
    margin={"r":0,"t":50,"l":0,"b":0},
    title_x=0.5,
    coloraxis_colorbar=dict(
        title="R$/m²",
        tickprefix="R$ ",
        ticks="outside"
    )
)

# Mostrar no navegador
fig_map.show(renderer="browser")

