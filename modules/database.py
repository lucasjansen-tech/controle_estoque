import streamlit as st
from gspread_pandas import Spread, Client
import pandas as pd
from google.oauth2.service_account import Credentials

def conectar_google_sheets():
    """
    Estabelece a conexão com as APIs do Google utilizando as 
    credenciais armazenadas nos Secrets do Streamlit.
    """
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # Busca as credenciais do ambiente (Secrets)
    creds_info = st.secrets["gcp_service_account"]
    credentials = Credentials.from_service_account_info(creds_info, scopes=scope)
    
    # Retorna o cliente autenticado para operações
    return Client(credentials=credentials)

def carregar_dados(aba_nome):
    """
    Acessa a planilha e retorna o conteúdo de uma aba específica.
    Mesmo que a tabela esteja vazia, retorna os cabeçalhos.
    """
    # Certifique-se de que o nome abaixo é o EXATO nome do arquivo no seu Google Drive
    nome_planilha = "Sistema_Estoque_Raposa" 
    
    try:
        client = conectar_google_sheets()
        # Inicializa a conexão com a planilha específica
        spread = Spread(nome_planilha, client=client)
        
        # Converte a aba solicitada para um DataFrame do Pandas
        # sheet_to_df(index=0) garante que a primeira linha seja o cabeçalho
        df = spread.sheet_to_df(sheet=aba_nome, index=0)
        
        return df
    except Exception as e:
        # Exibe o erro técnico caso a conexão falhe (ex: erro de chave ou permissão)
        st.error(f"Erro ao carregar a aba '{aba_nome}': {e}")
        return pd.DataFrame()
