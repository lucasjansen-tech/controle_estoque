import streamlit as st
from modules.auth import inicializar_sessao, realizar_logout
from views.login import renderizar_login

# Configurações iniciais da interface
st.set_page_config(
    page_title="Controle de Estoque - SEMED Raposa", 
    page_icon="📦", 
    layout="wide"
)

# 1. Inicializa a memória da sessão
inicializar_sessao()

# 2. Roteamento (Controle de Fluxo)
if not st.session_state['autenticado']:
    # Se NÃO estiver logado, tranca o usuário na tela de login
    renderizar_login()

else:
    # Se ESTIVER logado, monta a estrutura do sistema
    usuario = st.session_state['usuario_dados']
    
    # Monta a barra lateral (Sidebar)
    st.sidebar.title("Módulo Logístico")
    st.sidebar.write(f"Logado como: **{usuario['email']}**")
    st.sidebar.write(f"Nível de Acesso: **{usuario['perfil']}**")
    st.sidebar.divider()
    
    if st.sidebar.button("Sair do Sistema", use_container_width=True):
        realizar_logout()
        
    # Aqui vamos direcionar para a tela correta dependendo de quem logou
    if usuario['perfil'] == 'SEMED':
        st.header("🏢 Painel de Controle - Coordenação SEMED")
        st.write("Bem-vindo! Em breve, os módulos de Gestão de Catálogo, Escolas e Visão Macro aparecerão aqui.")
        # Futuramente: renderizar_semed()
        
    elif usuario['perfil'] == 'Escola':
        st.header("🏫 Painel da Unidade Escolar")
        st.write(f"Bem-vindo! Você está gerenciando o estoque da escola ID: {usuario['id_escola']}")
        # Futuramente: renderizar_escola()
