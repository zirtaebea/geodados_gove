from geopy.geocoders import Nominatim
import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon
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
        numero = row['nº_métrico_localização']
        distancia_em_metros = (numero)/100000
        # interpolando a distância conforme a distância do número métrico do início do logradouro
        # em lat long para visualizar
        # interpolacao = gdf_coord_invertido.interpolate(distancia_em_metros)

        # em utm
        interpolacao_utm = logradouro_utm.interpolate(distancia_em_metros)
        if interpolacao_utm.empty:
            print(
                f"Número de porta maior que o comprimento do logradouro encontrado no shapefile.")
            continue

        try:
            coordenada_final = (round(interpolacao_utm.geometry.x.iloc[0], 3),
                                round(interpolacao_utm.geometry.y.iloc[0], 3))

            resultado_com_coord = row.copy()
            resultado_com_coord['x_gove'] = coordenada_final[0]
            resultado_com_coord['y_gove'] = coordenada_final[1]
            resultado_com_coord['diferenca_x'] = (
                resultado_com_coord['x_gove'] - resultado_com_coord['coordenada_x'])
            resultado_com_coord['diferenca_y'] = (
                resultado_com_coord['y_gove'] - resultado_com_coord['coordenada_y'])
            resultados.append(resultado_com_coord)
        except IndexError:
            continue

    return resultados

    # para visualizar no mapa
    # lat_long = interpolacao.to_crs('EPSG: 4326')
    # coordenada_lat_long = (
    #     lat_long.geometry.x.iloc[0], lat_long.geometry.y.iloc[0])
    # mapa_ssa = folium.Map(location=[coordenada_lat_long[0], coordenada_lat_long[1]],
    #                     zoom_start=12,
    #                     tiles='OpenStreetMap',
    #                     name='Stamen')
    # folium.Marker([coordenada_lat_long[0], coordenada_lat_long[1]],
    #             popup=f'Localização Interpolada: {logradouro['Toponim']}, número {numero}').add_to(mapa_ssa)

    # # salva o mapa em um arquivo HTML para visualização
    # mapa_ssa.save('mapa_ssa.html')

    # return coordenada_final

# geometria setor fiscal + logradouro sedur medicao + interpolar/intersecção logradouro e setor fiscal
# pegar a coordenada do imovel e interpolar o setor fiscal
def setor_fiscal_correto(caminho_arquivo_log, caminho_arquivo_setor, nome_coluna_log, nome_coluna_nporta, coord_x, coord_y, nome_coluna_sfiscal, df):
    # abrindo shapefiles (.shp) pelo caminho do arquivo
    ssa_eixos = gpd.read_file(caminho_arquivo_log, crs='EPSG:31984')
    ssa_setor_fiscal = gpd.read_file(caminho_arquivo_setor, crs='EPSG:31984')
    resultados = []

    # localizando logradouro
    for index, row in df.iterrows():
        print(f"Processando linha {index}...")
        codlog = row[nome_coluna_log]

        # convertendo para lat_long
        logradouro = ssa_eixos[ssa_eixos['codlog'] == codlog]
        logradouro = logradouro.to_crs('EPSG:4326')

        if logradouro.empty:
            print(f"Logradouro {codlog} não encontrado no shapefile.")
            continue

        # GDF em UTM
        logradouro_utm = logradouro.to_crs('EPSG:31984')

        # transformando distância nº porta compatível à unidade de medida do logradouro em metros
        numero = row[nome_coluna_nporta]
        distancia_em_metros = numero / 100000

        if pd.notna(row.get(coord_x)) and pd.notna(row.get(coord_y)):
            try:
                # corrigindo o formato das coordenadas
                coord_x_val = float(str(row[coord_x]).replace(',', '.'))
                coord_y_val = float(str(row[coord_y]).replace(',', '.'))

                # localizando o imóvel por coordenada
                coordenada_existente = (coord_x_val, coord_y_val)
                localizacao = pd.DataFrame([row])
                localizacao['coordenadas'] = [Point(coordenada_existente)]
                localizacao = gpd.GeoDataFrame(localizacao, geometry='coordenadas', crs='EPSG:31984')

                # interseção entre ponto e polígono de setores fiscais
                intersecao_coord_existente = gpd.sjoin(localizacao, ssa_setor_fiscal, how='inner', predicate='within')

                if not intersecao_coord_existente.empty:
                    setor_fiscal_encontrado = intersecao_coord_existente.iloc[0]['Name']
                    setor_fiscal_original = row[nome_coluna_sfiscal]

                    if setor_fiscal_original != setor_fiscal_encontrado:
                        resultado_com_coord = pd.DataFrame([row])
                        resultado_com_coord['setor_fiscal_novo'] = setor_fiscal_encontrado
                        resultado_com_coord['analise_manual'] = 'nao'
                        resultados.append(resultado_com_coord)
            except (ValueError, IndexError) as e:
                print(f"Erro ao processar coordenadas ou interseção: {e}")
                continue

        else:
            if numero == 0:
                # se não tiver nº de porta, verificar se o logradouro possui interseção com mais de um setor fiscal
                intersecao_sem_n_porta = gpd.sjoin(logradouro, ssa_setor_fiscal, how='inner', predicate='within')
                try:
                    if not intersecao_sem_n_porta.empty:
                        setores_encontrados = intersecao_sem_n_porta['Name'].unique()
                        if len(setores_encontrados) > 1:
                            print(f"Logradouro {codlog} possui interseção com mais de um setor fiscal. Análise manual necessária.")
                            resultado_sem_coord = pd.DataFrame([row])
                            resultado_com_coord['setor_fiscal_novo'] = ''
                            resultado_sem_coord['analise_manual'] = 'sim (sem nº porta e com mais de 1 setor fiscal por logradouro)'
                            resultados.append(resultado_sem_coord)
                        else:
                            setor_fiscal_encontrado = setores_encontrados[0]
                            setor_fiscal_original = row[nome_coluna_sfiscal]
                            if setor_fiscal_original != setor_fiscal_encontrado:
                                resultado_sem_coord = pd.DataFrame([row])
                                resultado_sem_coord['setor_fiscal_novo'] = setor_fiscal_encontrado
                                resultado_sem_coord['analise_manual'] = 'nao'
                                resultados.append(resultado_sem_coord)
                except IndexError:
                    continue
                
            else:
                # interpolando a distância
                interpolacao_utm = logradouro_utm.interpolate(distancia_em_metros)
                if interpolacao_utm.empty:
                    print(f"Número de porta maior que o comprimento do logradouro encontrado no shapefile.")
                    continue
                try:
                    coordenada_final = (round(interpolacao_utm.geometry.x.iloc[0], 3), round(interpolacao_utm.geometry.y.iloc[0], 3))
                    resultado_com_coord = pd.DataFrame([row])
                    resultado_com_coord['geometry'] = [Point(coordenada_final)]
                    resultado_com_coord = gpd.GeoDataFrame(resultado_com_coord, geometry='geometry', crs='EPSG:31984')
                    # interseção com .shp de setor fiscal
                    intersecao_com_n_porta = gpd.sjoin(resultado_com_coord, ssa_setor_fiscal, how='inner', predicate='within')
                    if not intersecao_com_n_porta.empty:
                        setor_fiscal_encontrado = intersecao_com_n_porta.iloc[0]['Name']
                        setor_fiscal_original = row[nome_coluna_sfiscal]
                        if setor_fiscal_original != setor_fiscal_encontrado:
                            resultado_com_coord['setor_fiscal_novo'] = setor_fiscal_encontrado
                            resultado_com_coord['analise_manual'] = 'sim (com nº porta e com mais de 1 setor fiscal por logradouro)'
                            resultados.append(resultado_com_coord)
                except IndexError:
                    continue
    # retornando resultados concatenados
    if resultados:
        return pd.concat(resultados, ignore_index=True)
    else:
        print("Nenhum resultado para concatenar.")
        return pd.DataFrame()  # df vazio se não houver resultados


# correçao de bairro
def bairro_correcao(caminho_arquivo_log, caminho_arquivo_bairro, nome_coluna_log, nome_coluna_nporta, coord_x, coord_y, nome_coluna_bairro, df):
    # shapes
    ssa_eixos = gpd.read_file(caminho_arquivo_log, encoding='latin1')
    ssa_bairros = gpd.read_file(caminho_arquivo_bairro)
    
    print(ssa_eixos.columns)


    resultados = []

    # localizando logradouro
    for index, row in df.iterrows():
        print(f"Processando linha {index}...")
        codlog = row[nome_coluna_log]

        # selecionando logradouro correspondente
        logradouro = ssa_eixos[ssa_eixos['CÃ³digo _1'] == codlog]

        if logradouro.empty:
            print(f"Logradouro {codlog} não encontrado no shapefile.")
            continue

        # logradouro para UTM (EPSG:31984)
        logradouro_utm = logradouro.to_crs('EPSG:31984')

        # Distância com base no número de porta
        numero = row[nome_coluna_nporta]
        distancia_em_metros = pd.to_numeric(numero) / 100000  # Ajuste conforme a escala necessária


        if pd.notna(row.get(coord_x)) and pd.notna(row.get(coord_y)):
            try:
                # corrigindo o formato das coordenadas
                coord_x_val = float(str(row[coord_x]).replace(',', '.'))
                coord_y_val = float(str(row[coord_y]).replace(',', '.'))

                # criando GeoDataFrame a partir das coordenadas
                localizacao = gpd.GeoDataFrame(df.iloc[[index]], geometry=gpd.points_from_xy([
                                            coord_x_val], [coord_y_val]), crs='EPSG:31984')

                # verificando interseção com bairros
                intersecao_coord_existente = gpd.sjoin(
                    localizacao, ssa_bairros, how='inner', predicate='intersects')

                if not intersecao_coord_existente.empty:
                    bairro_encontrado = intersecao_coord_existente.iloc[0]['Bairro']
                    bairro_original = row[nome_coluna_bairro]

                    if bairro_original != bairro_encontrado:
                        resultado_com_coord = pd.DataFrame([row])
                        resultado_com_coord['bairro_novo'] = bairro_encontrado
                        resultado_com_coord['parametro'] = 'coordenada sedur'
                        resultado_com_coord['conclusão'] = 'bairro pela coordenada'
                        resultado_com_coord['analise_manual'] = 'sim'
                        resultados.append(resultado_com_coord)

            except (ValueError, IndexError) as e:
                print(f"Erro ao processar coordenadas ou interseção: {e}")
                continue

        else:
            if numero == 0:
                # verificar se o logradouro possui interseção com mais de um bairro
                intersecao_sem_n_porta = gpd.sjoin(
                    logradouro, ssa_bairros, how='inner', predicate='intersects')

                if not intersecao_sem_n_porta.empty:
                    bairros_encontrados = intersecao_sem_n_porta['Bairro'].unique(
                    )
                    if len(bairros_encontrados) > 1:
                        print(f"Logradouro {codlog} possui interseção com mais de um bairro. Análise manual necessária.")
                        resultado_sem_coord = pd.DataFrame([row])
                        resultado_sem_coord['bairro_novo'] = ''
                        resultado_sem_coord['parametro'] = 'interseção logradouro x bairro'
                        resultado_sem_coord['conclusão'] = 'logradouro com mais de 1 bairro. endereço sem nº de porta'
                        resultado_sem_coord['analise_manual'] = 'sim'
                        resultados.append(resultado_sem_coord)
                    else:
                        bairro_encontrado = bairros_encontrados[0]
                        bairro_original = row[nome_coluna_bairro]
                        if bairro_original != bairro_encontrado:
                            resultado_sem_coord = pd.DataFrame([row])
                            resultado_sem_coord['bairro_novo'] = bairro_encontrado
                            resultado_sem_coord['parametro'] = 'interseção logradouro x bairro'
                            resultado_sem_coord['conclusão'] = 'logradouro pertencente a apenas 1 bairro. endereço sem nº de porta'
                            resultado_sem_coord['analise_manual'] = 'nao'
                            resultados.append(resultado_sem_coord)

            else:
                # interpolando a distância para o número de porta
                interpolacao_utm = logradouro_utm.interpolate(
                    distancia_em_metros)
                if interpolacao_utm.empty:
                    print(
                        f"Número de porta maior que o comprimento do logradouro encontrado no shapefile.")
                    continue

                try:
                    # pegando a coordenada interpolada e criando GeoDataFrame
                    coordenada_final = Point(
                        interpolacao_utm.geometry.x.iloc[0], interpolacao_utm.geometry.y.iloc[0])
                    resultado_com_coord = gpd.GeoDataFrame(
                        [row], geometry=[coordenada_final], crs='EPSG:31984')

                    # intersecao bairros com numero de porta
                    intersecao_com_n_porta = gpd.sjoin(
                        resultado_com_coord, ssa_bairros, how='inner', predicate='intersects')
                    if not intersecao_com_n_porta.empty:
                        bairro_encontrado = intersecao_com_n_porta.iloc[0]['Bairro']
                        bairro_original = row[nome_coluna_bairro]

                        if bairro_original != bairro_encontrado:
                            resultado_com_coord['bairro_novo'] = bairro_encontrado
                            resultado_com_coord['parametro'] = 'localização bairro pelo logradouro e nº de porta'
                            resultado_com_coord['conclusão'] = 'bairro pelo endereço do imóvel'
                            resultado_com_coord['analise_manual'] = 'nao'
                            resultados.append(resultado_com_coord)

                except IndexError:
                    continue

    # retornando os resultados concatenados
    if resultados:
        return pd.concat(resultados, ignore_index=True)
    else:
        print("Nenhum resultado para concatenar.")
        return pd.DataFrame()  # Retorna DataFrame vazio


def dados_inscricoes_banco_enriquecimento(conn, ficha):
    try:
        query = """
            select ide_cadastro, cod_log_destinatario_enriquecido, nom_logradouro_match, 
            num_imovel_destinatario_enriquecido, nom_bairro_destinatario_enriquecido, 
            coordenada_geo_x_enriquecido, 
            coordenada_geo_y_enriquecido
            from salvador.enriquecimentos e 
            where e.ficha = %s 
            order by e.ide_cadastro asc
        """

        with conn.cursor() as cur:
            cur.execute(query, (ficha,))  # ficha é passado como tupla
            cadastros = cur.fetchall()
            return cadastros
    except Exception as e:
        print(f"Erro ao obter cadastros: {e}")
        return []
