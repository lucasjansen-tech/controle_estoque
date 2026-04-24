import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

def carregar_dados(aba_nome):
    """
    Lê os dados da planilha usando a biblioteca base gspread e converte para Pandas nativamente.
    Isso evita qualquer conflito de versão e garante estabilidade na nuvem.
    """
    nome_planilha = "Sistema_Estoque_Raposa"
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    try:
        # 1. Carrega as credenciais puras dos segredos
        creds_info = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(creds_info, scopes=scope)

        # 2. Autoriza e conecta diretamente pelo gspread oficial
        client = gspread.authorize(credentials)

        # 3. Abre a planilha e seleciona a aba
        planilha = client.open(nome_planilha)
        aba = planilha.worksheet(aba_nome)

        # 4. Puxa todos os valores (retorna uma lista de listas)
        dados = aba.get_all_values()

        # Se a aba estiver completamente vazia, retorna tabela vazia
        if not dados:
            return pd.DataFrame()

        # 5. Separa a primeira linha (cabeçalhos) do resto dos dados
        headers = dados[0]
        linhas = dados[1:]

        # 6. Converte para Pandas e retorna
        df = pd.DataFrame(linhas, columns=headers)
        return df

    except Exception as e:
        st.error(f"Erro ao carregar a aba '{aba_nome}': {e}")
        return pd.DataFrame()
