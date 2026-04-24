import streamlit as st
from modules.database import carregar_dados

def inicializar_sessao():
    if 'autenticado' not in st.session_state:
        st.session_state['autenticado'] = False
    if 'usuario_dados' not in st.session_state:
        st.session_state['usuario_dados'] = None

def realizar_login(email_digitado, senha_digitada):
    # 1. Verifica primeiro se é o Super Usuário (Root) nos Secrets
    root = st.secrets["root_user"]
    if email_digitado == root["email"] and senha_digitada == root["password"]:
        st.session_state['autenticado'] = True
        st.session_state['usuario_dados'] = {
            "id": "ROOT",
            "email": root["email"],
            "perfil": "SEMED", # O Root tem acesso total da coordenação
            "id_escola": None
        }
        return True

    # 2. Se não for Root, procura na planilha db_usuarios
    df_usuarios = carregar_dados("db_usuarios")
    if not df_usuarios.empty:
        usuario = df_usuarios[df_usuarios['Email'] == email_digitado]
        if not usuario.empty:
            senha_real = str(usuario.iloc[0]['Senha_Hash'])
            if str(senha_digitada) == senha_real:
                st.session_state['autenticado'] = True
                st.session_state['usuario_dados'] = {
                    "id": usuario.iloc[0]['ID_Usuario'],
                    "email": usuario.iloc[0]['Email'],
                    "perfil": usuario.iloc[0]['Perfil'],
                    "id_escola": usuario.iloc[0]['ID_Escola']
                }
                return True
    return False

def realizar_logout():
    st.session_state['autenticado'] = False
    st.session_state['usuario_dados'] = None
    st.rerun()

import gspread
from google.oauth2.service_account import Credentials

# Mantenha as funções carregar_dados e conectar_google_sheets como estão e adicione:

def salvar_dados(df_novo, aba_nome, modo='append'):
    """
    Salva dados na planilha. 
    'append' adiciona novas linhas. 
    'overwrite' substitui tudo (útil para edições em lote).
    """
    nome_planilha = "Sistema_Estoque_Raposa"
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    
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
