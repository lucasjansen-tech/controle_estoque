import streamlit as st
import pandas as pd
from datetime import datetime
from modules.database import carregar_dados, salvar_dados
from modules.logic import calcular_estoque_atual

def renderizar_semed():
    st.title("🏢 Gestão Central Logística - SEMED")
    
    eh_super_admin = st.session_state['usuario_dados']['id'] == "ROOT"

    menu = st.sidebar.radio("Navegar por:", [
        "📊 Dashboard de Saldo", 
        "🚚 Movimentar Carga", 
        "🏫 Unidades de Ensino", 
        "📂 Catálogo de Itens",
        "👥 Gestão de Usuários"
    ])

    st.sidebar.divider()
    if st.sidebar.button("🔄 Sincronizar Google Sheets", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # --- 1. DASHBOARD COM FILTROS ---
    if menu == "📊 Dashboard de Saldo":
        st.subheader("📊 Consulta de Estoque Real")
        
        df_escolas = carregar_dados("db_escolas")
        df_cat = carregar_dados("db_catalogo")
        
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            local = st.selectbox("Unidade:", ["SEMED"] + (df_escolas['ID_Escola'].tolist() if not df_escolas.empty else []))
        
        saldo = calcular_estoque_atual(local)
        
        if not saldo.empty:
            df_final = pd.merge(saldo, df_cat, on='ID_Produto', how='left')
            
            # Filtros de Visualização
            with st.expander("🔍 Filtros de Busca"):
                f_nome = st.text_input("Filtrar por Nome do Produto")
                f_cat = st.multiselect("Filtrar por Categoria", df_final['Categoria'].unique())
            
            # Aplicação dos filtros
            if f_nome:
                df_final = df_final[df_final['Nome_Produto'].str.contains(f_nome, case=False, na=False)]
            if f_cat:
                df_final = df_final[df_final['Categoria'].isin(f_cat)]
                
            st.dataframe(df_final[['ID_Produto', 'Nome_Produto', 'Saldo', 'Unidade', 'Categoria']], 
                         use_container_width=True, hide_index=True)
        else:
            st.info(f"Nenhum registro de estoque para {local}.")

    # --- 2. MOVIMENTAR CARGA ---
    elif menu == "🚚 Movimentar Carga":
        st.subheader("🚚 Registrar Fluxo de Material")
        df_cat = carregar_dados("db_catalogo")
        df_esc = carregar_dados("db_escolas")
        
        with st.form("form_mov_completo", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                origem_t = st.selectbox("Origem", ["Fornecedor", "Agricultura Familiar", "SEMED"])
                item = st.selectbox("Produto", df_cat['Nome_Produto'].tolist() if not df_cat.empty else [])
                qtd = st.number_input("Quantidade", min_value=0.1)
            with c2:
                destino = st.selectbox("Destino", ["SEMED"] + (df_esc['Nome_Escola'].tolist() if not df_esc.empty else []))
                doc = st.text_input("Nº Documento/Referência")
                data_m = st.date_input("Data", datetime.now())

            if st.form_submit_button("Confirmar Lançamento", use_container_width=True):
                id_p = df_cat[df_cat['Nome_Produto'] == item]['ID_Produto'].values[0]
                id_dest = "SEMED" if destino == "SEMED" else df_esc[df_esc['Nome_Escola'] == destino]['ID_Escola'].values[0]
                fluxo = "ENTRADA" if origem_t != "SEMED" else "TRANSFERÊNCIA"
                
                nova_mov = pd.DataFrame([[
                    f"MOV-{datetime.now().strftime('%y%m%d%H%M%S')}",
                    data_m.strftime('%d/%m/%Y'), id_dest, fluxo, origem_t, destino, id_p, qtd,
                    st.session_state['usuario_dados']['email'], doc
                ]], columns=['ID_Movimentacao', 'Data_Hora', 'ID_Escola', 'Tipo_Fluxo', 'Origem', 'Destino', 'ID_Produto', 'Quantidade', 'ID_Usuario', 'Documento_Ref'])
                
                if salvar_dados(nova_mov, "db_movimentacoes"):
                    st.success("Lançamento efetuado!")
                    st.rerun()

    # --- 3. UNIDADES DE ENSINO COM FILTROS E EDIÇÃO ---
    elif menu == "🏫 Unidades de Ensino":
        st.subheader("🏫 Gestão de Unidades")
        tipos_disponiveis = ["Creche", "Ensino Fundamental I", "Ensino Fundamental II", "EJA", "Tempo Integral"]
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            with st.expander("➕ Cadastro Individual"):
                with st.form("f_esc_ind"):
                    id_e = st.text_input("ID Escola")
                    nome_e = st.text_input("Nome da Unidade")
                    tipos_e = st.multiselect("Tipos de Ensino", tipos_disponiveis)
                    if st.form_submit_button("Salvar Escola"):
                        tipos_str = ", ".join(tipos_e)
                        salvar_dados(pd.DataFrame([[id_e, nome_e, tipos_str]], columns=['ID_Escola', 'Nome_Escola', 'Tipo_Escola']), "db_escolas")
                        st.rerun()
        with col_btn2:
            with st.expander("📥 Importar em Lote"):
                arq_e = st.file_uploader("Upload CSV/Excel", type=['csv', 'xlsx'])
                if arq_e and st.button("Processar Lote"):
                    df_l = pd.read_csv(arq_e) if arq_e.name.endswith('csv') else pd.read_excel(arq_e)
                    salvar_dados(df_l, "db_escolas", modo='append')
                    st.rerun()

        st.divider()
        df_e_view = carregar_dados("db_escolas")
        
        if not df_e_view.empty:
            with st.expander("🔍 Filtros de Visualização"):
                f_esc_nome = st.text_input("Buscar por Nome da Escola")
                f_esc_tipo = st.multiselect("Filtrar por Nível", tipos_disponiveis)
            
            if f_esc_nome:
                df_e_view = df_e_view[df_e_view['Nome_Escola'].str.contains(f_esc_nome, case=False, na=False)]
            if f_esc_tipo:
                # Filtra se algum dos tipos selecionados está na string de tipos da escola
                df_e_view = df_e_view[df_e_view['Tipo_Escola'].apply(lambda x: any(t in str(x) for t in f_esc_tipo))]

            st.write("📝 **Edição Rápida:** Clique nas células para alterar. Use o botão abaixo para confirmar.")
            df_e_edit = st.data_editor(df_e_view, num_rows="dynamic" if eh_super_admin else "fixed", use_container_width=True, hide_index=True)
            
            if st.button("💾 Salvar Alterações na Rede", use_container_width=True):
                if salvar_dados(df_e_edit, "db_escolas", modo='overwrite'):
                    st.success("Dados atualizados com sucesso!")

    # --- 4. CATÁLOGO DE ITENS COM FILTROS ---
    elif menu == "📂 Catálogo de Itens":
        st.subheader("📂 Gestão de Produtos")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            with st.expander("➕ Novo Item Individual"):
                with st.form("f_prod_ind"):
                    id_p = st.text_input("ID Produto")
                    nome_p = st.text_input("Nome")
                    cat_p = st.selectbox("Categoria", ["Alimentação", "Limpeza", "Expediente", "Pedagógico"])
                    un_p = st.selectbox("Unidade", ["Unid", "Kg", "Cx", "Pct", "Litro"])
                    if st.form_submit_button("Cadastrar Item"):
                        salvar_dados(pd.DataFrame([[id_p, nome_p, cat_p, un_p]], columns=['ID_Produto', 'Nome_Produto', 'Categoria', 'Unidade']), "db_catalogo")
                        st.rerun()
        with col_c2:
            with st.expander("📥 Importar Lote"):
                arq_p = st.file_uploader("Upload CSV/Excel", type=['csv', 'xlsx'], key="up_cat")
                if arq_p and st.button("Carregar Produtos"):
                    df_l_p = pd.read_csv(arq_p) if arq_p.name.endswith('csv') else pd.read_excel(arq_p)
                    salvar_dados(df_l_p, "db_catalogo", modo='append')
                    st.rerun()

        df_c_view = carregar_dados("db_catalogo")
        if not df_c_view.empty:
            with st.expander("🔍 Filtros de Catálogo"):
                f_p_nome = st.text_input("Buscar Produto")
                f_p_cat = st.multiselect("Categoria Item", df_c_view['Categoria'].unique())
            
            if f_p_nome:
                df_c_view = df_c_view[df_c_view['Nome_Produto'].str.contains(f_p_nome, case=False, na=False)]
            if f_p_cat:
                df_c_view = df_c_view[df_c_view['Categoria'].isin(f_p_cat)]

            df_c_edit = st.data_editor(df_c_view, num_rows="dynamic" if eh_super_admin else "fixed", use_container_width=True, hide_index=True)
            if st.button("💾 Atualizar Catálogo", use_container_width=True):
                salvar_dados(df_c_edit, "db_catalogo", modo='overwrite')
                st.success("Catálogo sincronizado!")

    # --- 5. GESTÃO DE USUÁRIOS COM FILTROS ---
    elif menu == "👥 Gestão de Usuários":
        st.subheader("👥 Controle de Acessos")
        df_esc_list = carregar_dados("db_escolas")
        
        with st.expander("➕ Criar Novo Acesso"):
            with st.form("f_user_add"):
                u_email = st.text_input("E-mail")
                u_pass = st.text_input("Senha")
                u_perfil = st.selectbox("Perfil", ["SEMED", "Escola"])
                u_vinculo = st.selectbox("Vínculo (ID Unidade)", ["SEMED"] + (df_esc_list['ID_Escola'].tolist() if not df_esc_list.empty else []))
                if st.form_submit_button("Gerar Usuário"):
                    id_u = f"USR-{datetime.now().strftime('%H%M%S')}"
                    salvar_dados(pd.DataFrame([[id_u, u_email, u_pass, u_perfil, u_vinculo]], columns=['ID_Usuario', 'Email', 'Senha_Hash', 'Perfil', 'ID_Escola']), "db_usuarios")
                    st.rerun()
        
        df_u_view = carregar_dados("db_usuarios")
        if not df_u_view.empty:
            with st.expander("🔍 Filtros de Usuários"):
                f_u_email = st.text_input("Buscar por E-mail")
                f_u_perf = st.multiselect("Perfil de Acesso", ["SEMED", "Escola"])
            
            if f_u_email:
                df_u_view = df_u_view[df_u_view['Email'].str.contains(f_u_email, case=False, na=False)]
            if f_u_perf:
                df_u_view = df_u_view[df_u_view['Perfil'].isin(f_u_perf)]

            df_u_edit = st.data_editor(df_u_view, num_rows="dynamic" if eh_super_admin else "fixed", use_container_width=True, hide_index=True)
            if st.button("💾 Salvar Alterações de Acessos", use_container_width=True):
                salvar_dados(df_u_edit, "db_usuarios", modo='overwrite')
                st.success("Lista de usuários atualizada!")
