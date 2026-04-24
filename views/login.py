import streamlit as st
from modules.auth import realizar_login

def renderizar_login():
    """Desenha a interface de login na tela."""
    
    # Cria colunas para centralizar o formulário na tela
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<h2 style='text-align: center;'>📦 Acesso ao Sistema</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>Rede Municipal de Ensino - Raposa</p>", unsafe_allow_html=True)
        st.write("") # Espaço em branco
        
        with st.form("form_login"):
            email = st.text_input("E-mail de acesso")
            senha = st.text_input("Senha", type="password")
            submit = st.form_submit_button("Entrar", use_container_width=True)
            
            if submit:
                if email == "" or senha == "":
                    st.warning("Por favor, preencha todos os campos.")
                else:
                    if realizar_login(email, senha):
                        st.success("Acesso liberado! Redirecionando...")
                        st.rerun() # Atualiza a página para carregar o sistema
                    else:
                        st.error("Credenciais inválidas. Verifique seu e-mail e senha.")
