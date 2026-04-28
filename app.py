import streamlit as st
from views.escola_view import renderizar_escola
from views.semed_view import renderizar_semed

def main():
    st.set_page_config(page_title="Gestão de Estoque - SEMED Raposa", page_icon="📦", layout="wide")

    # Verifica se o usuário já está logado na sessão
    if 'usuario_dados' not in st.session_state or not st.session_state['usuario_dados']:
        
        # ==========================================================
        # COLOQUE A SUA LÓGICA DE TELA DE LOGIN AQUI
        # (Os campos de st.text_input para e-mail e senha, e a 
        #  consulta ao db_usuarios para validar o acesso).
        # Após validar, não se esqueça de salvar os dados na sessão:
        # st.session_state['usuario_dados'] = {'Email': email_digitado, 'Perfil': perfil_banco, 'ID_Escola': id_escola_banco}
        # ==========================================================
        
        st.info("Por favor, faça o login para acessar o sistema.")
        return

    # --- O ROTEADOR CORRIGIDO E BLINDADO ---
    user_data = st.session_state['usuario_dados']
    email_logado = str(user_data.get('email', user_data.get('Email', ''))).strip()
    
    # Pega o perfil ignorando se veio maiúsculo ou minúsculo, e remove espaços
    perfil_bruto = user_data.get('perfil', user_data.get('Perfil', ''))
    perfil_usuario = str(perfil_bruto).strip().upper()

    # Validação de Segurança Extra: Verifica se o e-mail logado é o Admin do st.secrets
    eh_admin_master = False
    try:
        for k, v in st.secrets.items():
            if isinstance(v, str) and v == email_logado:
                eh_admin_master = True
            elif isinstance(v, dict):
                for sub_v in v.values():
                    if isinstance(sub_v, str) and sub_v == email_logado:
                        eh_admin_master = True
    except Exception:
        pass

    # Força a elevação se for o dono do sistema
    if eh_admin_master:
        perfil_usuario = 'ADMIN'

    # Direcionamento das Telas (Routing)
    if perfil_usuario == 'ESCOLA':
        renderizar_escola()
        
    elif perfil_usuario in ['SEMED', 'COORDENADOR', 'ADMIN', 'ADMINISTRADOR']:
        renderizar_semed()
        
    else:
        st.error(f"O perfil de acesso '{perfil_usuario}' não é válido no sistema.")
        if st.button("Sair e Tentar Novamente"):
            st.session_state.clear()
            st.rerun()

if __name__ == "__main__":
    main()
