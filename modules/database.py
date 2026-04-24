import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
from gspread_pandas import Spread

def carregar_dados(aba_nome):
    """
    Função robusta para carregar dados de uma aba específica da planilha no Google Drive.
    Projetada para funcionar no Streamlit Cloud usando credenciais dos Secrets.
    """
    nome_planilha = "Sistema_Estoque_Raposa"
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    try:
        # 1. Carrega as credenciais puras dos segredos.
        creds_info = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(creds_info, scopes=scope)

        # 2. Inicializa o objeto Spread, dizendo explicitamente para usar 
        # as credenciais carregadas, ignorando arquivos de configuração locais.
        # Isso resolve erros como "No client config found".
        # 'index=0' garante que os cabeçalhos serão lidos da primeira linha.
        spread = Spread(nome_planilha, creds=credentials, index=0)

        # 3. Lê o conteúdo da aba. Isso funcionará com a tabela vazia (com apenas cabeçalhos).
        # index=0 aqui diz que o Pandas não deve gerar um índice extra.
        df = spread.sheet_to_df(sheet=aba_nome, index=0)
        
        return df
    except Exception as e:
        # Se falhar na conexão ou formatação da chave
        st.error(f"Erro ao carregar a aba '{aba_nome}': {e}")
        return pd.DataFrame()
