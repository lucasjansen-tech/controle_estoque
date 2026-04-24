import streamlit as st
from gspread_pandas import Spread, Client
import pandas as pd
from google.oauth2.service_account import Credentials

def conectar_google_sheets():
    """Estabelece a conexão com as APIs do Google usando os segredos do Streamlit."""
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # Busca as credenciais configuradas na nuvem
    creds_info = st.secrets["gcp_service_account"]
    credentials = Credentials.from_service_account_info(creds_info, scopes=scope)
    
    return Client(credentials=credentials)

def carregar_dados(aba_nome):
    """Lê uma aba específica da planilha e retorna um DataFrame do Pandas."""
    # O nome deve ser exatamente igual ao do seu arquivo no Google Drive
    nome_planilha = "Sistema_Estoque_Raposa" 
    
    try:
        client = conectar_google_sheets()
        spread = Spread(nome_planilha, client=client)
        df = spread.sheet_to_df(sheet=aba_nome, index=0)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar a aba {aba_nome}: {e}")
        return pd.DataFrame()
