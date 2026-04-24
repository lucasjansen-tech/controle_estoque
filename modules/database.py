import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# 1. CACHE DE RECURSO: Mantém a conexão com o Google aberta sem precisar logar toda hora
@st.cache_resource
def conectar_google():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_info = st.secrets["gcp_service_account"]
    credentials = Credentials.from_service_account_info(creds_info, scopes=scope)
    return gspread.authorize(credentials)

# 2. CACHE DE DADOS: O app só lê a planilha de novo se passar 5 minutos (ttl=300)
# Isso impede o erro 429 quando muitos usuários entram ao mesmo tempo.
@st.cache_data(ttl=300) 
def carregar_dados(aba_nome):
    nome_planilha = "Sistema_Estoque_Raposa"
    try:
        client = conectar_google()
        planilha = client.open(nome_planilha)
        aba = planilha.worksheet(aba_nome)
        dados = aba.get_all_values()
        
        if not dados:
            return pd.DataFrame()
            
        # Converte em tabela Pandas usando a primeira linha como cabeçalho
        df = pd.DataFrame(dados[1:], columns=dados[0])
        return df
    except Exception as e:
        # Se der erro de cota (429), avisamos de forma amigável
        if "429" in str(e):
            st.warning("O sistema está sob alta carga. Os dados mostrados podem estar alguns minutos desatualizados.")
        else:
            st.error(f"Erro ao acessar a aba '{aba_nome}': {e}")
        return pd.DataFrame()

# 3. FUNÇÃO DE SALVAMENTO: Limpa o cache automaticamente após salvar
def salvar_dados(df_novo, aba_nome, modo='append'):
    nome_planilha = "Sistema_Estoque_Raposa"
    try:
        client = conectar_google()
        planilha = client.open(nome_planilha)
        aba = planilha.worksheet(aba_nome)
        
        if modo == 'append':
            aba.append_rows(df_novo.values.tolist())
        elif modo == 'overwrite':
            aba.clear()
            dados = [df_novo.columns.values.tolist()] + df_novo.values.tolist()
            aba.update('A1', dados)
        
        # Limpa o cache para que todos vejam o dado novo na próxima atualização
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Não foi possível salvar os dados: {e}")
        return False
