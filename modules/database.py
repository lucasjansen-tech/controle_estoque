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
