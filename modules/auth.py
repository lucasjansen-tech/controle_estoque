import streamlit as st
from modules.database import carregar_dados

def inicializar_sessao():
    """Cria as variáveis de sessão padrão ao abrir o sistema."""
    if 'autenticado' not in st.session_state:
        st.session_state['autenticado'] = False
    if 'usuario_dados' not in st.session_state:
        st.session_state['usuario_dados'] = None

def realizar_login(email_digitado, senha_digitada):
    """
    Busca o usuário na planilha e valida as credenciais.
    Retorna True se sucesso, False se falhar.
    """
    df_usuarios = carregar_dados("db_usuarios")
    
    if df_usuarios.empty:
        st.error("Banco de usuários indisponível ou vazio.")
        return False
        
    # Filtra a tabela procurando o e-mail digitado
    usuario = df_usuarios[df_usuarios['Email'] == email_digitado]
    
    if not usuario.empty:
        # Pega a senha daquele usuário específico
        senha_real = str(usuario.iloc[0]['Senha_Hash'])
        
        if str(senha_digitada) == senha_real:
            # Login com sucesso! Salva as informações na sessão
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
    """Limpa a sessão e desloga o usuário."""
    st.session_state['autenticado'] = False
    st.session_state['usuario_dados'] = None
    st.rerun() # Atualiza a página para aplicar a saída
