import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# Função interna para não repetir código de login
def autenticar_gspread():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_info = st.secrets["gcp_service_account"]
    credentials = Credentials.from_service_account_info(creds_info, scopes=scope)
    return gspread.authorize(credentials)

@st.cache_data(ttl=20) # Guarda os dados por 20 segundos para evitar o erro 429
def carregar_dados(aba_nome):
    nome_planilha = "Sistema_Estoque_Raposa"
    try:
        client = autenticar_gspread()
        planilha = client.open(nome_planilha)
        aba = planilha.worksheet(aba_nome)
        dados = aba.get_all_values()
        if not dados: return pd.DataFrame()
        return pd.DataFrame(dados[1:], columns=dados[0])
    except Exception as e:
        st.error(f"Erro ao carregar a aba '{aba_nome}': {e}")
        return pd.DataFrame()

def salvar_dados(df_novo, aba_nome, modo='append'):
    nome_planilha = "Sistema_Estoque_Raposa"
    try:
        client = autenticar_gspread()
        planilha = client.open(nome_planilha)
        aba = planilha.worksheet(aba_nome)
        
        if modo == 'append':
            aba.append_rows(df_novo.values.tolist())
        elif modo == 'overwrite':
            aba.clear()
            dados = [df_novo.columns.values.tolist()] + df_novo.values.tolist()
            aba.update('A1', dados)
        
        # Limpa o cache para que a próxima leitura já mostre o dado novo
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar na aba '{aba_nome}': {e}")
        return False
