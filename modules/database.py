import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

def carregar_dados(aba_nome):
    """
    Lê os dados da planilha usando a biblioteca base gspread e converte para Pandas nativamente.
    """
    nome_planilha = "Sistema_Estoque_Raposa"
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    try:
        creds_info = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(creds_info, scopes=scope)
        client = gspread.authorize(credentials)

        planilha = client.open(nome_planilha)
        aba = planilha.worksheet(aba_nome)
        dados = aba.get_all_values()

        if not dados:
            return pd.DataFrame()

        headers = dados[0]
        linhas = dados[1:]
        df = pd.DataFrame(linhas, columns=headers)
        return df

    except Exception as e:
        st.error(f"Erro ao carregar a aba '{aba_nome}': {e}")
        return pd.DataFrame()


def salvar_dados(df_novo, aba_nome, modo='append'):
    """
    Salva dados na planilha. 
    'append' adiciona novas linhas. 
    'overwrite' substitui tudo (útil para edições em lote).
    """
    nome_planilha = "Sistema_Estoque_Raposa"
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    try:
        creds_info = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(creds_info, scopes=scope)
        client = gspread.authorize(credentials)
        
        planilha = client.open(nome_planilha)
        aba = planilha.worksheet(aba_nome)
        
        if modo == 'append':
            # Converte DataFrame para lista de listas e ignora o cabeçalho
            dados = df_novo.values.tolist()
            aba.append_rows(dados)
            
        elif modo == 'overwrite':
            # Limpa a aba e escreve tudo de novo (cabeçalho + dados)
            aba.clear()
            dados = [df_novo.columns.values.tolist()] + df_novo.values.tolist()
            aba.update('A1', dados)
            
        return True
    except Exception as e:
        st.error(f"Erro ao salvar na aba '{aba_nome}': {e}")
        return False
