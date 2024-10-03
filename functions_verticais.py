import psycopg2
import pandas as pd
from collections import Counter

# funcion conexão db


def criar_conexao():
    try:
        conn = psycopg2.connect(
            host="xxxxxxxx",
            database="xxxxxx",
            user="xxxxx",
            password="xxxxxx"
        )
        return conn
    except Exception as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        return None


# function para pegar intervalo de inscrições ativas do mesmo conjunto
def intervalo_ativas_verticais(conn, cod_cliente, des_origem, cod_cadastro):
    try:
        tamanho_inscricao = len(cod_cadastro)

        if tamanho_inscricao in [5, 7]:  # verifica se o tamanho é válido
            # mantém todos os dígitos, exceto os dois últimos
            primeiros_digitos = cod_cadastro[:-2]
            # extrai o último dígito da insc sem dv
            ultimo_digito = int(primeiros_digitos[-1])

            if 0 <= ultimo_digito <= 9:
                # base do intervalo para capturar todos os cadastros que começam com os primeiros dígitos
                base_intervalo = f"{primeiros_digitos}%"

                print("Base do Intervalo:", base_intervalo)

                query = """
                    SELECT cod_cadastro, des_situacao_cadastro, num_imovel_1, num_hidrometro, cod_logradouro_1, num_sub_unidade, 
                        nom_edificio_1, nom_conjunto_habitacional_1, des_bloco_1, padrao_construtivo
                    FROM cadastro.cadastro
                    WHERE cod_cliente = %s
                    AND des_origem = %s
                    AND cod_cadastro LIKE %s
                    AND utilizacao = 'RESIDENCIAL VERTICAL'
                    AND des_situacao_cadastro = 'ATIVO'
                    AND LENGTH(cod_cadastro) = %s;
                """

                with conn.cursor() as cur:
                    # consulta usando a base do intervalo
                    cur.execute(query, (
                        cod_cliente,
                        des_origem,
                        base_intervalo,
                        tamanho_inscricao
                    ))
                    cadastros = cur.fetchall()

                    print("Resultado da consulta:", cadastros)

                    if cadastros:
                        # add resultados para um DataFrame
                        df_result = pd.DataFrame(cadastros, columns=[
                            'cod_cadastro', 'des_situacao_cadastro', 'num_imovel_1', 'num_hidrometro',
                            'cod_logradouro_1', 'num_sub_unidade', 'nom_edificio_1',
                            'nom_conjunto_habitacional_1', 'des_bloco_1', 'padrao_construtivo'
                        ])

                        # separa as linhas com sucesso e sem sucesso
                        df_intervalo = df_result[df_result['cod_cadastro'].notnull(
                        )]
                        df_sem_sucesso = df_result[df_result['cod_cadastro'].isnull(
                        )]

                        return df_intervalo, df_sem_sucesso
                    else:
                        print("Nenhum dado encontrado.")
                        return pd.DataFrame(), pd.DataFrame()  # df se não houver dados
        else:
            print("Tamanho da inscrição inválido.")
            return pd.DataFrame(), pd.DataFrame()

    except Exception as e:
        print(f"Erro ao obter cadastros: {e}")
        return pd.DataFrame(), pd.DataFrame()


# function para definir moda do padrão construtivo
def moda_padrao_construtivo(df_intervalo, inscricao):
    # primeiros 5 dígitos da inscrição fornecida (ou menos)
    primeiros_digitos = inscricao[:5]  # 5 dígitos da inscrição

    # filtro com base nos primeiros 5 dígitos do 'cod_cadastro'
    df_filtrado = df_intervalo[df_intervalo['cod_cadastro'].str[:5]
                               == primeiros_digitos]

    # moda de 'padrao_construtivo' para os registros filtrados
    if not df_filtrado.empty:
        frequencia = Counter(df_filtrado['padrao_construtivo'])
        moda = frequencia.most_common(1)[0][0]  # pega o valor mais comum
        return moda
    else:
        return None  # retorna nane se não tiver nenhuma correspondência


# function para armazenar moda do padrão construtivo das inscrições do conjunto
def criar_df_com_moda(df_intervalo, inscricoes):
    # Lista para armazenar os resultados
    resultados = []

    # calcula a moda para cada inscrição
    for inscricao in inscricoes:  # itera sobre a lista de inscrições
        moda = moda_padrao_construtivo(df_intervalo, inscricao)
        resultados.append({'inscricao': inscricao, 'moda': moda})

    # resultados em DataFrame
    df_resultado = pd.DataFrame(resultados)
    return df_resultado
