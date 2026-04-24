import streamlit as st
import pandas as pd
from modules.database import carregar_dados

def calcular_estoque_atual(id_local):
    """
    Soma as entradas e subtrai as saídas para dar o saldo real de um local.
    id_local pode ser 'SEMED' ou o ID de uma escola (ex: 'ESC-01').
    """
    # 1. Carrega os dados usando o nosso novo cache (evita erro 429)
    df_mov = carregar_dados("db_movimentacoes")
    
    if df_mov is None or df_mov.empty:
        return pd.DataFrame(columns=['ID_Produto', 'Saldo'])

    # 2. Garante que a coluna 'Quantidade' seja tratada como número
    # Usamos o nome exato da sua planilha: 'Quantidade'
    df_mov['Quantidade'] = pd.to_numeric(df_mov['Quantidade'], errors='coerce').fillna(0)

    # 3. Filtramos as movimentações pertencentes ao local selecionado
    # Usamos a sua coluna: 'ID_Escola'
    df_local = df_mov[df_mov['ID_Escola'] == id_local].copy()

    if df_local.empty:
        return pd.DataFrame(columns=['ID_Produto', 'Saldo'])

    # 4. Lógica de Sinal (O que entra e o que sai)
    # De acordo com seu Tipo_Fluxo: ENTRADA/TRANSFERÊNCIA (+) e SAÍDA (-)
    def definir_sinal(tipo):
        tipo_limpo = str(tipo).strip().upper()
        if tipo_limpo in ['ENTRADA', 'TRANSFERÊNCIA']:
            return 1
        elif tipo_limpo == 'SAÍDA':
            return -1
        return 0 # Caso haja algum tipo desconhecido

    df_local['Multiplicador'] = df_local['Tipo_Fluxo'].apply(definir_sinal)
    df_local['Qtd_Calculada'] = df_local['Quantidade'] * df_local['Multiplicador']

    # 5. Agrupa por ID_Produto e gera o saldo final
    estoque_final = df_local.groupby('ID_Produto')['Qtd_Calculada'].sum().reset_index()
    estoque_final.columns = ['ID_Produto', 'Saldo']
    
    return estoque_final
