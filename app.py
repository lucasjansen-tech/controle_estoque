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
                    # Garante que os nomes das colunas não tenham espaços ocultos
                    df_usuarios.columns = df_usuarios.columns.str.strip()
                    
                    col_senha = 'Senha_Hash' if 'Senha_Hash' in df_usuarios.columns else 'Senha'
                    
                    if 'Email' in df_usuarios.columns and col_senha in df_usuarios.columns:
                        
                        # Higienização
                        df_usuarios['Email_Check'] = df_usuarios['Email'].astype(str).str.strip().str.lower()
                        df_usuarios['Senha_Check'] = df_usuarios[col_senha].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                        
                        email_limpo = str(email_digitado).strip().lower()
                        senha_limpa = str(senha_digitada).strip()
                        
                        # Busca o usuário
                        usuario_encontrado = df_usuarios[(df_usuarios['Email_Check'] == email_limpo) & (df_usuarios['Senha_Check'] == senha_limpa)]
                        
                        if not usuario_encontrado.empty:
                            dados = usuario_encontrado.iloc[0]
                            st.session_state['usuario_dados'] = {
                                'email': dados['Email'],
                                'perfil': dados['Perfil'],
                                'id_escola': dados.get('ID_Escola', '')
                            }
                            st.success("Login realizado com sucesso!")
                            st.rerun()
                        else:
                            st.cache_data.clear()
                            st.error("E-mail ou senha incorretos.")
                            
                            # --- MODO DETETIVE LIGADO ---
                            st.warning("🔍 MODO DEBUG ATIVADO: Veja abaixo o porquê o sistema está negando o acesso:")
                            st.info(f"O que você digitou -> E-mail: '{email_limpo}' | Senha: '{senha_limpa}'")
                            st.info(f"E-mails encontrados no banco: {df_usuarios['Email_Check'].tolist()}")
                            st.info(f"Senhas encontradas no banco: {df_usuarios['Senha_Check'].tolist()}")
                            # -----------------------------
                    else:
                        st.error(f"Erro estrutural: Colunas 'Email' ou '{col_senha}' não encontradas. Colunas atuais no banco: {df_usuarios.columns.tolist()}")
                else:
                    st.warning("Base de usuários ('db_usuarios') não encontrada ou vazia.")
            else:
                st.warning("Preencha todos os campos para entrar.")
        
        # Trava a tela aqui até o login ocorrer com sucesso
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
    except Exception: 
        pass

    # Direcionamento
    if perfil_usuario == 'ESCOLA':
        renderizar_escola()
    elif perfil_usuario in ['SEMED', 'COORDENADOR', 'ADMIN', 'ADMINISTRADOR']:
        renderizar_semed()
    else:
        st.error(f"Perfil '{perfil_usuario}' não autorizado.")
        if st.button("Sair"):
            st.session_state.clear()
            st.rerun()

if __name__ == "__main__":
    main()
