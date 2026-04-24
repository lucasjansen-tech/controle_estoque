import pandas as pd
from modules.database import carregar_dados

def calcular_estoque_atual(id_local):
    """
    Soma todas as entradas e subtrai as saídas de um local específico 
    (SEMED ou uma Escola) para entregar o saldo atualizado.
    """
    df_mov = carregar_dados("db_movimentacoes")
    
    if df_mov.empty:
        return pd.DataFrame(columns=['ID_Produto', 'Saldo'])

    # Garantir que a coluna de quantidade seja numérica para não dar erro no cálculo
    df_mov['Quantidade_Movimentada'] = pd.to_numeric(df_mov['Quantidade_Movimentada'], errors='coerce').fillna(0)

    # 1. Filtramos apenas as movimentações do local que queremos ver (SEMED ou Escola X)
    df_local = df_mov[df_mov['ID_Escola'] == id_local].copy()

    if df_local.empty:
        return pd.DataFrame(columns=['ID_Produto', 'Saldo'])

    # 2. Criamos uma lógica de sinal: 
    # ENTRADA e TRANSFERÊNCIA aumentam o estoque (+)
    # SAÍDA (consumo ou perda) diminui o estoque (-)
    def definir_sinal(tipo):
        if tipo in ['ENTRADA', 'TRANSFERÊNCIA']:
            return 1
        return -1

    df_local['Multiplicador'] = df_local['Tipo'].apply(definir_sinal)
    df_local['Qtd_Ajustada'] = df_local['Quantidade_Movimentada'] * df_local['Multiplicador']

    # 3. Agrupamos por produto e somamos tudo
    estoque_final = df_local.groupby('ID_Produto')['Qtd_Ajustada'].sum().reset_index()
    estoque_final.columns = ['ID_Produto', 'Saldo']
    
    return estoque_final
