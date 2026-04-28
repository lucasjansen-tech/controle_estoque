import streamlit as st
from views.escola_view import renderizar_escola
from views.semed_view import renderizar_semed

def main():
    st.set_page_config(page_title="Sistema de Estoque - SEMED Raposa", page_icon="📦", layout="wide")

    # 1. VERIFICAÇÃO DE LOGIN
    if 'usuario_dados' not in st.session_state or not st.session_state['usuario_dados']:
        st.markdown("<h2 style='text-align: center; color: #004a99;'>Acesso ao Sistema SEMED</h2>", unsafe_allow_html=True)
        
        with st.form("form_login"):
            email_digitado = st.text_input("E-mail")
            senha_digitada = st.text_input("Senha", type="password")
            btn_login = st.form_submit_button("Entrar", type="primary")

        if btn_login:
            if email_digitado and senha_digitada:
                from modules.database import carregar_dados
                df_usuarios = carregar_dados("db_usuarios")
                
                if not df_usuarios.empty:
                    usuario_encontrado = df_usuarios[(df_usuarios['Email'] == email_digitado) & (df_usuarios['Senha_Hash'] == senha_digitada)]
                    
                    if not usuario_encontrado.empty:
                        dados = usuario_encontrado.iloc[0]
                        st.session_state['usuario_dados'] = {
                            'email': dados['Email'],
                            'perfil': dados['Perfil'],
                            'id_escola': dados.get('ID_Escola', '')
                        }
                        st.success("Login realizado!")
                        st.rerun()
                    else:
                        st.error("E-mail ou senha incorretos.")
                else:
                    st.warning("Base de usuários não encontrada.")
            else:
                st.warning("Preencha todos os campos.")
        return

    # 2. ROTEADOR DE TELAS
    user_data = st.session_state['usuario_dados']
    email_logado = str(user_data.get('email', '')).strip()
    perfil_usuario = str(user_data.get('perfil', '')).strip().upper()

    # Detecção automática de Admin Master via Secrets
    try:
        for k, v in st.secrets.items():
            if isinstance(v, str) and v == email_logado:
                perfil_usuario = 'ADMIN'
            elif isinstance(v, dict):
                for sub_v in v.values():
                    if isinstance(sub_v, str) and sub_v == email_logado:
                        perfil_usuario = 'ADMIN'
    except Exception: pass

    if perfil_usuario == 'ESCOLA':
        renderizar_escola()
    elif perfil_usuario in ['SEMED', 'COORDENADOR', 'ADMIN', 'ADMINISTRADOR']:
        renderizar_semed()
    else:
        st.error(f"Perfil '{perfil_usuario}' não autorizado.")
        if st.sidebar.button("Sair"):
            st.session_state.clear()
            st.rerun()

if __name__ == "__main__":
    main()
