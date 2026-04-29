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
                    # 1. Garante que os nomes das colunas não tenham espaços escondidos
                    df_usuarios.columns = df_usuarios.columns.str.strip()
                    
                    col_senha = 'Senha_Hash' if 'Senha_Hash' in df_usuarios.columns else 'Senha'
                    
                    if 'Email' in df_usuarios.columns and col_senha in df_usuarios.columns:
                        
                        # 2. Tratamento Extremo: Força texto, minúsculas e remove o ".0" fantasma
                        df_usuarios['Email_Check'] = df_usuarios['Email'].astype(str).str.strip().str.lower()
                        df_usuarios['Senha_Check'] = df_usuarios[col_senha].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                        
                        email_limpo = str(email_digitado).strip().lower()
                        senha_limpa = str(senha_digitada).strip()
                        
                        # 3. Busca o usuário com os dados higienizados
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
                            # 4. BALA DE PRATA: Limpa o cache se errar, para forçar atualização
                            st.cache_data.clear()
                            st.error("E-mail ou senha incorretos. (Se você acabou de alterar a senha, tente novamente agora).")
                    else:
                        st.error(f"Erro no banco: Colunas 'Email' ou '{col_senha}' não encontradas.")
                else:
                    st.warning("Base de usuários não encontrada ou vazia.")
            else:
                st.warning("Preencha todos os campos para entrar.")
        
        # Esse return trava a tela aqui até o login ser feito
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

    # Direciona para as views corretas
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
