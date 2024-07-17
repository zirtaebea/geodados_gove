from geopy.geocoders import Nominatim
import geopandas as gpd
from shapely.geometry import Point, LineString
import osmnx as ox
import brazilcep
import requests
import pandas as pd
import urllib.parse
import folium
import re


# Endereço por número do cep
def endereco_por_cep(cep):
    try:
        endereco = brazilcep.get_address_from_cep(cep)
        return endereco
    except Exception as e:
        print(f"Erro ao consultar CEP: {e}")
        return None


# Verificador de cep por bairro (no caso de ter várias ruas com o mesmo nome em bairros diferentes)
def verifica_cep_bairro(dicionario_ceps, nome_bairro):
    df_cep = pd.DataFrame(dicionario_ceps)
    filtro_bairro = df_cep[df_cep['bairro'] == nome_bairro]
    if not filtro_bairro.empty:
        cep_final = filtro_bairro['cep'].tolist()
        print(cep_final)
        return cep_final


# função auxiliar da verifica_metragem_log_e_numero_porta
# Coordenadas por endereço por extenso
def coordenadas_por_endereco(localizacao, usuario):
    geolocator = Nominatim(user_agent=usuario)
    location = geolocator.geocode(localizacao)
    if location:
        return (location.latitude, location.longitude)
    else:
        print("Endereço não encontrado")
        return None


# Verifica o número de porta em relação a metragem do logradouro
def verifica_metragem_log_e_numero_porta(cep, numero, usuario):
    endereco = endereco_por_cep(cep)
    if cep:
        rua = endereco['street']
        bairro = endereco['district']
        cidade = endereco['city']
        estado = endereco['uf']
        endereco_completo = f"{rua}, {bairro}, {cidade}, {estado}, Brasil"
        coordenadas = coordenadas_por_endereco(endereco_completo, usuario)

        if coordenadas:
            latitude, longitude = coordenadas
            # baixar os dados do log usando osmnx
            graph = ox.graph_from_point(
                (latitude, longitude), dist=1000, network_type='all', simplify=True)
            # Converter p GeoDataFrames
            nodes, edges = ox.graph_to_gdfs(graph)
            # filtrar p acessar a rua desejada
            street_edges = edges[edges['name'].str.contains(
                rua, case=False, na=False)]

            if not street_edges.empty:
                # calcular o comprimento total do log
                street_length = street_edges['length'].sum()
                print(f"Comprimento da {rua}: {street_length} metros")
                if numero > street_length:
                    print(
                        'Número de porta maior que o comprimento do logradouro, probabilidade de estar errado')
                else:
                    print(f'Número de porta {
                        numero} é válido para o comprimento do logradouro')
            else:
                print(f"Não foi possível encontrar a {
                      rua} em {endereco_completo}")
        else:
            print("Não foi possível obter as coordenadas para o endereço")
    else:
        print("Não foi possível obter dados para o endereço")


# Encontra cep de acordo com o nome do logradouro
def verifica_log_cep(uf, cidade, nome_rua):
    try:
        nome_rua_codificado = urllib.parse.quote(nome_rua)
        url = f'https://viacep.com.br/ws/{uf}/{
            cidade}/{nome_rua_codificado}/json/'
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        resultados_ceps = []
        if isinstance(data, list) and len(data) > 0:
            for enderecos in data:
                resultado = {
                    'cep': enderecos['cep'],
                    'bairro': enderecos['bairro']
                }
                resultados_ceps.append(resultado)
            return resultados_ceps
        else:
            print(f"Não foi possível encontrar o CEP para {
                  nome_rua}, {cidade}.")
            return None
    except requests.exceptions.RequestException as req_err:
        print(f'Erro de requisição ao consultar CEP: {req_err}')
    except Exception as e:
        print(f'Erro ao consultar CEP: {e}')
    return None


# função auxiliar da coordenada_numero_porta
# Inverter ordem das cooordenadas
def inverter_coordenadas(geom):
    if geom and geom.geom_type == 'LineString':
        coords_invertidas = [(p[1], p[0]) for p in geom.coords]
        return LineString(coords_invertidas)
    else:
        return geom
# for codlog in coluna_log
#   logradouro ssa_eixos[ssa_eixos['CodLog'] == codlog]

# Coordenadas de acordo com a extensão do shp do logradouro e número de porta


def coordenada_numero_porta(caminho_pc, df):
    # abrindo shapefile pelo caminho do arquivo
    ssa_eixos = gpd.read_file(caminho_pc, crs='EPSG:31984')
    resultados = []

    for index, row in df.iterrows():
        print(f"Processando linha {index}...")
        codlog = row['cod._logradouro_localização']
        codlog = int(re.sub(r'-\d+', '', codlog))

        # convertendo para lat_long
        logradouro = ssa_eixos[ssa_eixos['CodLog'] == codlog]
        logradouro = logradouro.to_crs('EPSG: 4326')
        
        if logradouro.empty:
            print(f"Logradouro {codlog} não encontrado no shapefile.") 
            continue
        # invertendo coordenadas para visualização
        gdf_coord_invertido = logradouro.copy()
        gdf_coord_invertido['geometry'] = logradouro['geometry'].apply(
            inverter_coordenadas)

        # geodataframe em utm
        logradouro_utm = logradouro.to_crs('EPSG:31984')

        # transformando distância nº métrico compatível a unidade de medida do logradouro
        numero = row['nº_métrico_localização'] # numero = row['nº_porta_localização'] (caso seja utilizado o código com número de porta sem alfanumérico)
        distancia_em_metros = (numero)/100000
        
        # interpolando a distância conforme a distância do número métrico/porta do início do logradouro
        # em lat long para visualizar
        # interpolacao = gdf_coord_invertido.interpolate(distancia_em_metros)

        # em utm
        interpolacao_utm = logradouro_utm.interpolate(distancia_em_metros)
        if interpolacao_utm.empty:
            print("Número de porta não encontrado no logradouro encontrado no shapefile.") 
            continue
        
        try:
            coordenada_final = (round(interpolacao_utm.geometry.x.iloc[0], 3), 
                                round(interpolacao_utm.geometry.y.iloc[0], 3))
            
            resultado_com_coord = row.copy()
            resultado_com_coord['x_gove'] = coordenada_final[0]
            resultado_com_coord['y_gove'] = coordenada_final[1]
            resultado_com_coord['diferenca_x'] = (resultado_com_coord['x_gove'] - resultado_com_coord['coordenada_x'])
            resultado_com_coord['diferenca_y'] = (resultado_com_coord['y_gove'] - resultado_com_coord['coordenada_y'])
            resultados.append(resultado_com_coord)
        except IndexError:
            continue

    return resultados
