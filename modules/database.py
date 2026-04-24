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

        # 2. Inicializa o objeto Spread com as credenciais (sem o index aqui!)
        spread = Spread(nome_planilha, creds=credentials)

        # 3. Lê o conteúdo da aba e transforma em tabela do Pandas
        # index=None garante que todas as colunas sejam mantidas como dados normais
        df = spread.sheet_to_df(sheet=aba_nome, index=None)
        
        return df
    except Exception as e:
        st.error(f"Erro ao carregar a aba '{aba_nome}': {e}")
        return pd.DataFrame()
