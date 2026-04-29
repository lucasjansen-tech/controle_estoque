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
                
                # Prepara os dados digitados para comparação
                email_limpo_input = str(email_digitado).strip().lower()
                senha_limpa_input = str(senha_digitada).strip()
                
                # ==========================================
                # 🚀 O ATALHO DO SUPER ADMIN (FANTASMA)
                # Lê exatamente a estrutura [root_user] do seu ficheiro secrets
                # ==========================================
                try:
                    admin_email = st.secrets["root_user"]["email"].lower()
                    admin_senha = st.secrets["root_user"]["password"]
                except KeyError:
                    # Se não encontrar o bloco no secrets, assume valores de bloqueio
                    admin_email = "admin_desativado"
                    admin_senha = "senha_desativada"
                
                if email_limpo_input == admin_email and senha_limpa_input == admin_senha:
                    st.session_state['usuario_dados'] = {
                        'email': 'Super Admin',
                        'perfil': 'ADMIN',
                        'id_escola': 'NENHUMA (Acesso Global)'
                    }
                    st.success("Acesso Master liberado!")
                    st.rerun()
                    
                # ==========================================
                # 👥 LOGIN NORMAL (VIA PLANILHA DB_USUARIOS)
                # ==========================================
                else:
                    from modules.database import carregar_dados
                    df_usuarios = carregar_dados("db_usuarios")
                    
                    if not df_usuarios.empty:
                        df_usuarios.columns = df_usuarios.columns.str.strip()
                        
                        col_senha = 'Senha_Hash' if 'Senha_Hash' in df_usuarios.columns else 'Senha'
                        
                        if 'Email' in df_usuarios.columns and col_senha in df_usuarios.columns:
                            
                            df_usuarios['Email_Check'] = df_usuarios['Email'].astype(str).str.strip().str.lower()
                            df_usuarios['Senha_Check'] = df_usuarios[col_senha].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                            
                            usuario_encontrado = df_usuarios[(df_usuarios['Email_Check'] == email_limpo_input) & (df_usuarios['Senha_Check'] == senha_limpa_input)]
                            
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
                                st.error("E-mail ou palavra-passe incorretos.")
                        else:
                            st.error(f"Erro estrutural: Colunas 'Email' ou '{col_senha}' não encontradas na base de dados.")
                    else:
                        st.warning("Base de utilizadores ('db_usuarios') não encontrada ou vazia.")
            else:
                st.warning("Preencha todos os campos para entrar.")
        
        return

    # 2. ROTEADOR DE ECRÃS
    user_data = st.session_state['usuario_dados']
    perfil_usuario = str(user_data.get('perfil', '')).strip().upper()

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
