import streamlit as st
from modules.auth import inicializar_sessao, realizar_login, realizar_logout
from views.semed_view import renderizar_semed
from views.escola_view import renderizar_escola

# Configuração da Página (Deve ser a primeira linha de código Streamlit)
st.set_page_config(
    page_title="Sistema de Estoque - SEMED Raposa",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializa as variáveis de controle de acesso
inicializar_sessao()

def main():
    # --- TELA DE LOGIN ---
    if not st.session_state['autenticado']:
        st.container()
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            st.title("🔐 Acesso ao Sistema")
            st.write("Insira suas credenciais para gerenciar o estoque da rede.")
            
            with st.form("form_login"):
                email = st.text_input("E-mail ou Usuário")
                senha = st.text_input("Senha", type="password")
                botao_entrar = st.form_submit_button("Entrar", use_container_width=True)
                
                if botao_entrar:
                    if realizar_login(email, senha):
                        st.success("Login realizado com sucesso!")
                        st.rerun()
                    else:
                        st.error("Credenciais inválidas. Verifique seu e-mail e senha.")

    # --- TELA LOGADA ---
    else:
        # Barra Lateral de Controle
        with st.sidebar:
            st.image("https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcR0Y6I7k-Fj-5vF-N4S2W_rI7T0G3N-u-X8_w&s", width=100) # Exemplo de Logo
            st.write(f"👤 **{st.session_state['usuario_dados']['email']}**")
            st.write(f"🏷️ Perfil: {st.session_state['usuario_dados']['perfil']}")
            
            if st.button("🚪 Sair do Sistema", use_container_width=True):
                realizar_logout()

        # Roteamento por Perfil
        perfil = st.session_state['usuario_dados']['perfil']
        
        if perfil == "SEMED":
            renderizar_semed()
        elif perfil == "Escola":
            renderizar_escola()

if __name__ == "__main__":
    main()
