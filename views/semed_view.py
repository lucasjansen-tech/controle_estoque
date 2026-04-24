import streamlit as st
import pandas as pd
from datetime import datetime
from modules.database import carregar_dados, salvar_dados
from modules.logic import calcular_estoque_atual

def renderizar_semed():
    st.title("🏢 Gestão Central - SEMED Raposa")
    st.info(f"Painel Administrativo: {st.session_state['usuario_dados']['email']}")

    # Organização do Sistema por Abas
    tab_dash, tab_mov, tab_esc, tab_prod, tab_user = st.tabs([
        "📊 Dashboard de Saldo", 
        "🚚 Registrar Movimentação", 
        "🏫 Escolas", 
        "📂 Catálogo", 
        "👥 Usuários"
    ])

    # --- ABA 1: DASHBOARD DE SALDO (O QUE TEM NO ESTOQUE AGORA) ---
    with tab_dash:
        st.subheader("Consultar Estoque em Tempo Real")
        df_escolas_list = carregar_dados("db_escolas")
        
        # Seletor para ver estoque da SEMED ou de uma Escola específica
        local_selecionado = st.selectbox(
            "Selecione o local para verificar o saldo:", 
            ["SEMED"] + df_escolas_list['ID_Escola'].tolist() if not df_escolas_list.empty else ["SEMED"]
        )
        
        saldo = calcular_estoque_atual(local_selecionado)
        
        if not saldo.empty:
            df_catalogo = carregar_dados("db_produtos")
            # Une o saldo com o catálogo para mostrar o nome do produto
            df_final = pd.merge(saldo, df_catalogo, on='ID_Produto', how='left')
            st.write(f"### Saldo atual em: **{local_selecionado}**")
            st.dataframe(df_final[['Nome_Produto', 'Saldo', 'Unidade', 'Categoria']], use_container_width=True)
        else:
            st.warning("Nenhuma movimentação encontrada para este local.")

    # --- ABA 2: REGISTRAR MOVIMENTAÇÃO (AÇÕES DE ENTREGA E AGRICULTURA) ---
    with tab_mov:
        st.subheader("📦 Lançar Entrada ou Saída de Material")
        
        df_prod = carregar_dados("db_produtos")
        df_esc = carregar_dados("db_escolas")
        
        with st.form("fluxo_estoque"):
            col1, col2 = st.columns(2)
            
            with col1:
                origem_tipo = st.selectbox("Origem do Material", [
                    "Agricultura Familiar (Direto na Escola)", 
                    "Fornecedor Terceirizado", 
                    "Estoque Central SEMED (Transferência)"
                ])
                produto_nome = st.selectbox("Item", df_prod['Nome_Produto'].tolist() if not df_prod.empty else [])
                qtd = st.number_input("Quantidade", min_value=1)
                
            with col2:
                destino_nome = st.selectbox("Destino da Entrega", ["SEMED"] + df_esc['Nome_Escola'].tolist() if not df_esc.empty else ["SEMED"])
                doc_ref = st.text_input("Documento de Referência (Nº Nota/Guia/Foto)")
                data_manual = st.date_input("Data do Recebimento", datetime.now())

            if st.form_submit_button("Confirmar Registro"):
                # Busca IDs necessários
                id_p = df_prod[df_prod['Nome_Produto'] == produto_nome]['ID_Produto'].values[0]
                id_dest = "SEMED" if destino_nome == "SEMED" else df_esc[df_esc['Nome_Escola'] == destino_nome]['ID_Escola'].values[0]
                
                # Define se é entrada (aumenta estoque) ou saída (diminui)
                # Para seu banco, ID_Escola é o local onde o estoque está sendo alterado
                tipo_mov = "ENTRADA" if "Agricultura" in origem_tipo or "Fornecedor" in origem_tipo else "TRANSFERÊNCIA"

                nova_mov = pd.DataFrame([[
                    f"MOV-{datetime.now().strftime('%y%m%d%H%M%S')}",
                    data_manual.strftime('%Y-%m-%d %H:%M:%S'),
                    id_dest,
                    tipo_mov,
                    id_p,
                    qtd,
                    st.session_state['usuario_dados']['email'],
                    doc_ref
                ]], columns=['ID_Movimentacao', 'Data_Hora', 'ID_Escola', 'Tipo', 'ID_Produto', 'Quantidade_Movimentada', 'ID_Usuario', 'Documento_Ref'])
                
                if salvar_dados(nova_mov, "db_movimentacoes", modo='append'):
                    st.success("Movimentação registrada com sucesso!")
                    st.rerun()

    # --- ABA 3: GESTÃO DE ESCOLAS (INDIVIDUAL E LOTE) ---
    with tab_esc:
        st.subheader("Gerenciar Unidades Escolares")
        with st.expander("➕ Cadastrar/Importar Escolas"):
            c1, c2 = st.columns(2)
            with c1:
                with st.form("add_esc"):
                    id_e = st.text_input("Código/ID")
                    nome_e = st.text_input("Nome da Escola")
                    tipo_e = st.selectbox("Tipo", ["Creche", "Fundamental", "EJA", "Outros"])
                    if st.form_submit_button("Salvar"):
                        salvar_dados(pd.DataFrame([[id_e, nome_e, tipo_e]], columns=['ID_Escola', 'Nome_Escola', 'Tipo']), "db_escolas")
                        st.rerun()
            with c2:
                file_esc = st.file_uploader("Importar Lote (Excel/CSV)", type=['xlsx', 'csv'], key="f_esc")
                if file_esc and st.button("Carregar Lote Escolas"):
                    df_lote = pd.read_csv(file_esc) if file_esc.name.endswith('csv') else pd.read_excel(file_esc)
                    salvar_dados(df_lote, "db_escolas", modo='append')
                    st.rerun()

        df_esc_view = carregar_dados("db_escolas")
        if not df_esc_view.empty:
            df_edit = st.data_editor(df_esc_view, num_rows="dynamic", use_container_width=True)
            if st.button("Salvar Alterações nas Escolas"):
                salvar_dados(df_edit, "db_escolas", modo='overwrite')
                st.rerun()

    # --- ABA 4: CATÁLOGO DE PRODUTOS ---
    with tab_prod:
        st.subheader("Gerenciar Itens do Catálogo")
        with st.expander("➕ Adicionar Produtos"):
            with st.form("add_prod"):
                colp1, colp2 = st.columns(2)
                id_p = colp1.text_input("ID Produto")
                nome_p = colp1.text_input("Nome do Item")
                cat_p = colp2.selectbox("Categoria", ["Alimentação", "Limpeza", "Expediente", "Pedagógico"])
                uni_p = colp2.selectbox("Unidade", ["Unid", "Kg", "Litro", "Cx", "Pct"])
                if st.form_submit_button("Cadastrar Item"):
                    salvar_dados(pd.DataFrame([[id_p, nome_p, cat_p, uni_p]], columns=['ID_Produto', 'Nome_Produto', 'Categoria', 'Unidade']), "db_produtos")
                    st.rerun()

        df_prod_view = carregar_dados("db_produtos")
        if not df_prod_view.empty:
            df_p_edit = st.data_editor(df_prod_view, num_rows="dynamic", use_container_width=True)
            if st.button("Salvar Alterações no Catálogo"):
                salvar_dados(df_p_edit, "db_produtos", modo='overwrite')
                st.rerun()

    # --- ABA 5: GESTÃO DE USUÁRIOS ---
    with tab_user:
        st.subheader("Controle de Acesso")
        with st.expander("➕ Novo Usuário"):
            with st.form("add_user"):
                email_u = st.text_input("E-mail")
                pass_u = st.text_input("Senha")
                perf_u = st.selectbox("Perfil", ["SEMED", "Escola"])
                id_esc_u = st.selectbox("Vínculo", ["SEMED"] + df_escolas_list['ID_Escola'].tolist() if not df_escolas_list.empty else ["SEMED"])
                if st.form_submit_button("Criar Usuário"):
                    id_u = f"USR-{email_u.split('@')[0].upper()}"
                    salvar_dados(pd.DataFrame([[id_u, email_u, pass_u, perf_u, id_esc_u]], columns=['ID_Usuario', 'Email', 'Senha_Hash', 'Perfil', 'ID_Escola']), "db_usuarios")
                    st.rerun()

        df_user_view = carregar_dados("db_usuarios")
        if not df_user_view.empty:
            df_u_edit = st.data_editor(df_user_view, num_rows="dynamic", use_container_width=True)
            if st.button("Salvar Alterações de Usuários"):
                salvar_dados(df_u_edit, "db_usuarios", modo='overwrite')
                st.rerun()
