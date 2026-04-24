import pandas as pd
from modules.database import carregar_dados

def calcular_estoque_atual(id_local):
    df_mov = carregar_dados("db_movimentacoes")
    
    if df_mov is None or df_mov.empty:
        return pd.DataFrame(columns=['ID_Produto', 'Saldo'])

    # Ajuste para os seus nomes de coluna exatos
    df_mov['Quantidade'] = pd.to_numeric(df_mov['Quantidade'], errors='coerce').fillna(0)

    # Filtramos onde o Destino é o local atual
    df_local = df_mov[df_mov['ID_Escola'] == id_local].copy()

    if df_local.empty:
        return pd.DataFrame(columns=['ID_Produto', 'Saldo'])

    # Definir sinal com base na sua coluna Tipo_Fluxo
    def definir_sinal(tipo):
        if tipo in ['ENTRADA', 'TRANSFERÊNCIA']:
            return 1
        return -1

    df_local['Multiplicador'] = df_local['Tipo_Fluxo'].apply(definir_sinal)
    df_local['Qtd_Ajustada'] = df_local['Quantidade'] * df_local['Multiplicador']

    estoque_final = df_local.groupby('ID_Produto')['Qtd_Ajustada'].sum().reset_index()
    estoque_final.columns = ['ID_Produto', 'Saldo']
    
    return estoque_final
