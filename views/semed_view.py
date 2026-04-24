import streamlit as st
import pandas as pd
from datetime import datetime
from modules.database import carregar_dados, salvar_dados
from modules.logic import calcular_estoque_atual

def renderizar_semed():
    st.title("🏢 Gestão Central Logística - SEMED")
    
    # Identifica se é o Super Usuário (Dono do Sistema)
    eh_super_admin = st.session_state['usuario_dados']['id'] == "ROOT"

    menu = st.sidebar.radio("Navegar por:", [
        "📊 Dashboard de Saldo", 
        "🚚 Movimentar Carga", 
        "🏫 Unidades de Ensino", 
        "📂 Catálogo de Itens",
        "👥 Gestão de Usuários"
    ])

    st.sidebar.divider()
    if st.sidebar.button("🔄 Sincronizar Google Sheets"):
        st.cache_data.clear()
        st.rerun()

    # --- 1. DASHBOARD ---
    if menu == "📊 Dashboard de Saldo":
        st.subheader("Consulta de Estoque Real")
        df_escolas = carregar_dados("db_escolas")
        opcoes = ["SEMED"] + (df_escolas['ID_Escola'].tolist() if not df_escolas.empty else [])
        local = st.selectbox("Selecione a Unidade:", opcoes)
        
        saldo = calcular_estoque_atual(local)
        if not saldo.empty:
            df_cat = carregar_dados("db_catalogo")
            df_final = pd.merge(saldo, df_cat, on='ID_Produto', how='left')
            st.dataframe(df_final[['Nome_Produto', 'Saldo', 'Unidade', 'Categoria']], use_container_width=True, hide_index=True)
        else:
            st.info(f"Nenhum registro de estoque para {local}.")

    # --- 2. MOVIMENTAR CARGA ---
    elif menu == "🚚 Movimentar Carga":
        st.subheader("Registrar Fluxo de Material")
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

            if st.form_submit_button("Confirmar Lançamento"):
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

    # --- 3. UNIDADES DE ENSINO (Com tipos detalhados e trava de exclusão) ---
    elif menu == "🏫 Unidades de Ensino":
        st.subheader("Gestão de Unidades")
        tipos_disponiveis = ["Creche", "Ensino Fundamental I", "Ensino Fundamental II", "EJA", "Tempo Integral"]
        
        col_a, col_b = st.columns(2)
        with col_a:
            with st.expander("➕ Cadastro Individual"):
                with st.form("f_esc_ind"):
                    id_e = st.text_input("ID Escola")
                    nome_e = st.text_input("Nome da Unidade")
                    tipos_e = st.multiselect("Tipos de Ensino", tipos_disponiveis)
                    if st.form_submit_button("Salvar Escola"):
                        tipos_str = ", ".join(tipos_e)
                        salvar_dados(pd.DataFrame([[id_e, nome_e, tipos_str]], columns=['ID_Escola', 'Nome_Escola', 'Tipo_Escola']), "db_escolas")
                        st.rerun()
        with col_b:
            with st.expander("📥 Importar Escolas em Lote"):
                arq_e = st.file_uploader("Arquivo CSV/Excel (Colunas: ID_Escola, Nome_Escola, Tipo_Escola)", type=['csv', 'xlsx'])
                if arq_e and st.button("Processar Lote Escolas"):
                    df_l = pd.read_csv(arq_e) if arq_e.name.endswith('csv') else pd.read_excel(arq_e)
                    salvar_dados(df_l, "db_escolas", modo='append')
                    st.rerun()

        st.write("---")
        df_e_view = carregar_dados("db_escolas")
        if not df_e_view.empty:
            # Trava: num_rows="dynamic" só é True se for ROOT (permite deletar)
            df_e_edit = st.data_editor(df_e_view, num_rows="dynamic" if eh_super_admin else "fixed", use_container_width=True, hide_index=True)
            if st.button("💾 Salvar Alterações / Exclusões (Unidades)"):
                salvar_dados(df_e_edit, "db_escolas", modo='overwrite')
                st.success("Tabela de escolas atualizada!")

    # --- 4. CATÁLOGO DE ITENS ---
    elif menu == "📂 Catálogo de Itens":
        st.subheader("Gestão de Produtos")
        col_c, col_d = st.columns(2)
        with col_c:
            with st.expander("➕ Novo Item Individual"):
                with st.form("f_prod_ind"):
                    id_p = st.text_input("ID Produto")
                    nome_p = st.text_input("Nome")
                    cat_p = st.selectbox("Categoria", ["Alimentação", "Limpeza", "Expediente"])
                    un_p = st.selectbox("Unidade", ["Unid", "Kg", "Cx", "Pct"])
                    if st.form_submit_button("Cadastrar Item"):
                        salvar_dados(pd.DataFrame([[id_p, nome_p, cat_p, un_p]], columns=['ID_Produto', 'Nome_Produto', 'Categoria', 'Unidade']), "db_catalogo")
                        st.rerun()
        with col_d:
            with st.expander("📥 Importar Catálogo em Lote"):
                arq_p = st.file_uploader("Arquivo CSV/Excel", type=['csv', 'xlsx'])
                if arq_p and st.button("Processar Lote Catálogo"):
                    df_l_p = pd.read_csv(arq_p) if arq_p.name.endswith('csv') else pd.read_excel(arq_p)
                    salvar_dados(df_l_p, "db_catalogo", modo='append')
                    st.rerun()

        df_c_view = carregar_dados("db_catalogo")
        if not df_c_view.empty:
            df_c_edit = st.data_editor(df_c_view, num_rows="dynamic" if eh_super_admin else "fixed", use_container_width=True, hide_index=True)
            if st.button("💾 Salvar Alterações / Exclusões (Catálogo)"):
                salvar_dados(df_c_edit, "db_catalogo", modo='overwrite')
                st.success("Catálogo atualizado!")

    # --- 5. GESTÃO DE USUÁRIOS ---
    elif menu == "👥 Gestão de Usuários":
        st.subheader("Controle de Usuários e Funcionários")
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
            df_u_edit = st.data_editor(df_u_view, num_rows="dynamic" if eh_super_admin else "fixed", use_container_width=True, hide_index=True)
            if st.button("💾 Salvar Alterações / Exclusões (Usuários)"):
                salvar_dados(df_u_edit, "db_usuarios", modo='overwrite')
                st.success("Acessos atualizados!")
