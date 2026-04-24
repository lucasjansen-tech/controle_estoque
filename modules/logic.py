import pandas as pd
from modules.database import carregar_dados

def calcular_estoque_atual(id_local):
    """
    Calcula o saldo real baseando-se na aba db_movimentacoes.
    """
    df_mov = carregar_dados("db_movimentacoes")
    
    if df_mov is None or df_mov.empty:
        return pd.DataFrame(columns=['ID_Produto', 'Saldo'])

    # Garante que a quantidade seja numérica (Coluna: Quantidade)
    df_mov['Quantidade'] = pd.to_numeric(df_mov['Quantidade'], errors='coerce').fillna(0)

    # Filtra pelo ID da Escola ou SEMED (Coluna: ID_Escola)
    df_local = df_mov[df_mov['ID_Escola'] == id_local].copy()

    if df_local.empty:
        return pd.DataFrame(columns=['ID_Produto', 'Saldo'])

    # Lógica de sinal baseada na sua coluna: Tipo_Fluxo
    def definir_sinal(tipo):
        tipo_limpo = str(tipo).strip().upper()
        if tipo_limpo in ['ENTRADA', 'TRANSFERÊNCIA']:
            return 1
        elif tipo_limpo == 'SAÍDA':
            return -1
        return 0

    df_local['Multiplicador'] = df_local['Tipo_Fluxo'].apply(definir_sinal)
    df_local['Qtd_Calculada'] = df_local['Quantidade'] * df_local['Multiplicador']

    # Agrupa por ID_Produto e gera o saldo
    estoque_final = df_local.groupby('ID_Produto')['Qtd_Calculada'].sum().reset_index()
    estoque_final.columns = ['ID_Produto', 'Saldo']
    
    return estoque_final
