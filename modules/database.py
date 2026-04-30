import streamlit as st
import pandas as pd
import gspread
import time
from google.oauth2.service_account import Credentials

# --- MOTOR DE RESILIÊNCIA (RETRY LOGIC) ---
def executar_com_retry(funcao, max_tentativas=3, espera_inicial=2):
    """
    Tenta executar uma operação no Google Sheets.
    Se houver erro de cota (429) ou instabilidade na API, 
    espera alguns segundos e tenta novamente.
    """
    for tentativa in range(max_tentativas):
        try:
            return funcao()
        except Exception as e:
            # Erro 429 é excesso de requisições. 1001/500/503 são instabilidades do Google.
            mensagens_retry = ["429", "APIError", "INTERNAL_SERVER_ERROR", "Quota exceeded"]
            if any(msg in str(e) for msg in mensagens_retry):
                if tentativa < max_tentativas - 1:
                    tempo_pausa = espera_inicial * (tentativa + 1)
                    time.sleep(tempo_pausa)
                    continue
            # Se não for erro de cota ou acabarem as tentativas, repassa o erro
            raise e

# 1. CONEXÃO COM CACHE
@st.cache_resource
def conectar_google():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_info = st.secrets["gcp_service_account"]
    credentials = Credentials.from_service_account_info(creds_info, scopes=scope)
    return gspread.authorize(credentials)

# 2. CARREGAMENTO COM PROTEÇÃO
@st.cache_data(ttl=300) 
def carregar_dados(aba_nome):
    nome_planilha = "Sistema_Estoque_Raposa"
    
    def _operacao():
        client = conectar_google()
        planilha = client.open(nome_planilha)
        aba = planilha.worksheet(aba_nome)
        dados = aba.get_all_values()
        if not dados:
            return pd.DataFrame()
        return pd.DataFrame(dados[1:], columns=dados[0])

    try:
        # Tenta carregar usando o motor de retry
        return executar_com_retry(_operacao)
    except Exception as e:
        st.error(f"Erro persistente ao carregar '{aba_nome}': {e}")
        return pd.DataFrame()

# 3. SALVAMENTO BLINDADO (FEEDBACK VISUAL + RETRY)
def salvar_dados(df_novo, aba_nome, modo='append'):
    nome_planilha = "Sistema_Estoque_Raposa"
    
    def _operacao():
        client = conectar_google()
        planilha = client.open(nome_planilha)
        aba = planilha.worksheet(aba_nome)
        
        if modo == 'append':
            aba.append_rows(df_novo.values.tolist())
        elif modo == 'overwrite':
            aba.clear()
            dados = [df_novo.columns.values.tolist()] + df_novo.values.tolist()
            aba.update('A1', dados)
        return True

    # O spinner cria o bloqueio visual (UX) para evitar o clique duplo
    with st.spinner(f"Sincronizando com a base de dados..."):
        try:
            sucesso = executar_com_retry(_operacao)
            if sucesso:
                # Limpa o cache para garantir que a rede veja o dado novo imediatamente
                st.cache_data.clear()
                return True
        except Exception as e:
            st.error(f"Falha crítica no salvamento após várias tentativas: {e}")
            return False
def gerar_id_sequencial(prefixo, df_alvo, coluna_id):
    """
    Gera um ID sequencial no formato PREFIXO-001 (ex: ESC-001, USR-001).
    """
    if df_alvo.empty or coluna_id not in df_alvo.columns:
        return f"{prefixo}-001"
    
    ids_existentes = df_alvo[coluna_id].dropna().astype(str)
    ids_filtrados = ids_existentes[ids_existentes.str.startswith(f"{prefixo}-")]
    
    if ids_filtrados.empty:
        return f"{prefixo}-001"
        
    numeros = []
    for val in ids_filtrados:
        try:
            num = int(val.split('-')[1])
            numeros.append(num)
        except ValueError:
            pass 
            
    if not numeros:
        return f"{prefixo}-001"
        
    proximo_num = max(numeros) + 1
    return f"{prefixo}-{proximo_num:03d}"
