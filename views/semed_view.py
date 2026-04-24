import streamlit as st
import pandas as pd
from modules.database import carregar_dados, salvar_dados

def renderizar_semed():
    st.title("🏢 Gestão Central - SEMED Raposa")
    st.info(f"Bem-vindo, Super Admin. Use as abas abaixo para alimentar e editar o sistema.")

    # Criação das abas principais
    tab_escolas, tab_produtos, tab_usuarios = st.tabs([
        "🏫 Unidades Escolares", 
        "📦 Catálogo de Produtos", 
        "👥 Gestão de Usuários"
    ])

    # --- ABA 1: UNIDADES ESCOLARES ---
    with tab_escolas:
        st.subheader("Gerenciar Escolas")
        
        col1, col2 = st.columns(2)
        with col1:
            with st.expander("➕ Cadastrar Escola Individual"):
                with st.form("form_escola_individual"):
                    id_esc = st.text_input("ID/Código da Escola")
                    nome_esc = st.text_input("Nome da Unidade")
                    tipo_esc = st.selectbox("Tipo", ["Creche", "Ensino Fundamental I", "Ensino Fundamental II", "EJA", "SEMED"])
                    if st.form_submit_button("Salvar Escola"):
                        novo_df = pd.DataFrame([[id_esc, nome_esc, tipo_esc]], columns=['ID_Escola', 'Nome_Escola', 'Tipo'])
                        if salvar_dados(novo_df, "db_escolas", modo='append'):
                            st.success("Escola cadastrada com sucesso!")
                            st.rerun()

        with col2:
            with st.expander("📥 Importar Escolas em Lote"):
                arquivo_esc = st.file_uploader("Suba um CSV/Excel (Colunas: ID_Escola, Nome_Escola, Tipo)", type=['csv', 'xlsx'], key="up_esc")
                if arquivo_esc:
                    df_lote_esc = pd.read_csv(arquivo_esc) if arquivo_esc.name.endswith('csv') else pd.read_excel(arquivo_esc)
                    if st.button("Confirmar Carga de Escolas"):
                        if salvar_dados(df_lote_esc, "db_escolas", modo='append'):
                            st.success("Lote de escolas importado!")
                            st.rerun()

        st.divider()
        st.write("### Lista de Unidades (Edite diretamente na tabela)")
        df_esc_atual = carregar_dados("db_escolas")
        if not df_esc_atual.empty:
            df_esc_editado = st.data_editor(df_esc_atual, num_rows="dynamic", use_container_width=True, key="editor_esc")
            if st.button("Aplicar Alterações nas Escolas"):
                if salvar_dados(df_esc_editado, "db_escolas", modo='overwrite'):
                    st.success("Alterações salvas!")
                    st.rerun()

    # --- ABA 2: CATÁLOGO DE PRODUTOS ---
    with tab_produtos:
        st.subheader("Catálogo de Itens")
        
        col1, col2 = st.columns(2)
        with col1:
            with st.expander("➕ Cadastrar Novo Produto"):
                with st.form("form_produto"):
                    id_prod = st.text_input("Código do Produto (SKU)")
                    nome_prod = st.text_input("Nome do Item")
                    cat_prod = st.selectbox("Categoria", ["Material Escolar", "Limpeza", "Merenda", "Expediente", "Mobiliário"])
                    unid_prod = st.selectbox("Unidade de Medida", ["Unidade", "Caixa", "Pacote", "Quilo", "Litro"])
                    if st.form_submit_button("Salvar Produto"):
                        novo_prod_df = pd.DataFrame([[id_prod, nome_prod, cat_prod, unid_prod]], 
                                                  columns=['ID_Produto', 'Nome_Produto', 'Categoria', 'Unidade'])
                        if salvar_dados(novo_prod_df, "db_produtos", modo='append'):
                            st.success("Produto adicionado ao catálogo!")
                            st.rerun()

        with col2:
            with st.expander("📥 Importar Catálogo em Lote"):
                arquivo_prod = st.file_uploader("Suba CSV/Excel (Colunas: ID_Produto, Nome_Produto, Categoria, Unidade)", type=['csv', 'xlsx'], key="up_prod")
                if arquivo_prod:
                    df_lote_prod = pd.read_csv(arquivo_prod) if arquivo_prod.name.endswith('csv') else pd.read_excel(arquivo_prod)
                    if st.button("Confirmar Carga de Produtos"):
                        if salvar_dados(df_lote_prod, "db_produtos", modo='append'):
                            st.success("Catálogo atualizado com sucesso!")
                            st.rerun()

        st.divider()
        df_prod_atual = carregar_dados("db_produtos")
        if not df_prod_atual.empty:
            df_prod_editado = st.data_editor(df_prod_atual, num_rows="dynamic", use_container_width=True, key="editor_prod")
            if st.button("Salvar Alterações no Catálogo"):
                if salvar_dados(df_prod_editado, "db_produtos", modo='overwrite'):
                    st.success("Catálogo sincronizado!")

    # --- ABA 3: GESTÃO DE USUÁRIOS ---
    with tab_usuarios:
        st.subheader("Controle de Acesso (Administradores e Diretores)")
        
        with st.expander("➕ Criar Novo Usuário"):
            with st.form("form_user"):
                u_email = st.text_input("E-mail de Login")
                u_pass = st.text_input("Senha Inicial")
                u_perfil = st.selectbox("Perfil de Acesso", ["SEMED", "Escola"])
                # Busca lista de IDs de escolas para vincular
                lista_escolas = carregar_dados("db_escolas")['ID_Escola'].tolist() if not df_esc_atual.empty else ["ROOT"]
                u_escola = st.selectbox("Vincular à Unidade", ["Nenhum (Admin)"] + lista_escolas)
                
                if st.form_submit_button("Criar Usuário"):
                    id_u = f"USR-{u_email.split('@')[0].upper()}"
                    novo_user_df = pd.DataFrame([[id_u, u_email, u_pass, u_perfil, u_escola]], 
                                              columns=['ID_Usuario', 'Email', 'Senha_Hash', 'Perfil', 'ID_Escola'])
                    if salvar_dados(novo_user_df, "db_usuarios", modo='append'):
                        st.success(f"Usuário {u_email} criado!")
                        st.rerun()

        st.divider()
        df_users_atual = carregar_dados("db_usuarios")
        if not df_users_atual.empty:
            st.write("Usuários Registrados (Exceto Super Admin)")
            df_u_editado = st.data_editor(df_users_atual, num_rows="dynamic", use_container_width=True, key="editor_users")
            if st.button("Salvar Alterações de Usuários"):
                if salvar_dados(df_u_editado, "db_usuarios", modo='overwrite'):
                    st.success("Lista de usuários atualizada!")
