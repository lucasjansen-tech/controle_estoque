import streamlit as st
import pandas as pd
from datetime import datetime
from modules.database import carregar_dados, salvar_dados
from modules.logic import calcular_estoque_atual

def renderizar_escola():
    # Recupera os dados do usuário logado
    user_data = st.session_state['usuario_dados']
    id_escola = user_data['id_escola']
    
    # Busca o nome da escola para o cabeçalho
    df_esc_ref = carregar_dados("db_escolas")
    nome_escola = "Unidade Escolar"
    if not df_esc_ref.empty:
        info = df_esc_ref[df_esc_ref['ID_Escola'] == id_escola]
        if not info.empty:
            nome_escola = info.iloc[0]['Nome_Escola']

    st.title(f"🏫 Portal da Escola: {nome_escola}")
    st.caption(f"Operador: {user_data['email']} | ID: {id_escola}")

    # --- Menu Lateral e Dicas (UX) ---
    menu = st.sidebar.radio("Ações Disponíveis:", [
        "📊 Painel de Estoque", 
        "📥 Receber Material (Lote)", 
        "🍳 Registrar Consumo",
        "📂 Novo Item (Agricultura)",
        "📜 Meus Relatórios"
    ])

    st.sidebar.divider()
    
    # Dicas Dinâmicas na Lateral
    if menu == "📥 Receber Material (Lote)":
        st.sidebar.info("""
        **💡 Como receber vários itens:**
        1. Preencha os dados da entrega (Origem/Nota).
        2. Na tabela, clique em 'Add Row' (+) para cada produto novo.
        3. Selecione o produto e digite a quantidade.
        4. Clique no botão de confirmação no final.
        """)
    elif menu == "🍳 Registrar Consumo":
        st.sidebar.warning("""
        **⚠️ Atenção:**
        O registro de consumo deve ser feito diariamente para que o estoque da rede esteja sempre atualizado.
        """)

    if st.sidebar.button("🔄 Atualizar Dados", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # --- 1. PAINEL DE ESTOQUE (Login da Escola) ---
    if menu == "📊 Painel de Estoque":
        st.subheader("📊 Resumo de Prateleira")
        
        saldo = calcular_estoque_atual(id_escola)
        df_cat = carregar_dados("db_catalogo")
        
        if not saldo.empty:
            df_final = pd.merge(saldo, df_cat, on='ID_Produto', how='left')
            
            # Métricas Rápidas
            m1, m2 = st.columns(2)
            m1.metric("Itens Cadastrados", len(df_final))
            m2.metric("Total em Saldo", f"{df_final['Saldo'].sum():.0f} unidades")
            
            st.divider()
            f_busca = st.text_input("🔍 Procurar item no meu estoque:", help="Digite o nome do produto para filtrar.")
            if f_busca:
                df_final = df_final[df_final['Nome_Produto'].str.contains(f_busca, case=False, na=False)]
            
            st.dataframe(df_final[['Nome_Produto', 'Saldo', 'Unidade_Medida', 'Categoria']], 
                         use_container_width=True, hide_index=True)
        else:
            st.info("Bem-vindo! Seu estoque está zerado. Registre sua primeira entrega na aba 'Receber Material'.")

    # --- 2. RECEBIMENTO EM LOTE (Múltiplos Produtos) ---
    elif menu == "📥 Receber Material (Lote)":
        st.subheader("📥 Entrada de Materiais (Múltiplos Itens)")
        st.write("Use esta tela para dar entrada em tudo o que chegou na escola em uma única guia/nota.")
        
        df_cat = carregar_dados("db_catalogo")
        
        # 1. Dados da Guia/Entrega
        with st.container(border=True):
            col1, col2, col3 = st.columns(3)
            origem = col1.selectbox("Origem", ["Agricultura Familiar", "SEMED", "Fornecedor"], help="De onde veio o material?")
            doc_ref = col2.text_input("Nº Documento/Guia", help="Campo obrigatório para auditoria.")
            data_r = col3.date_input("Data de Recebimento", datetime.now(), format="DD/MM/YYYY")

        st.write("📝 **Lista de Produtos Recebidos:**")
        # 2. Tabela para múltiplos itens
        df_items_input = pd.DataFrame(columns=['Produto', 'Quantidade'])
        
        # Configuração das colunas para o editor
        config = {
            "Produto": st.column_config.SelectboxColumn("Produto", options=df_cat['Nome_Produto'].unique(), required=True),
            "Quantidade": st.column_config.NumberColumn("Qtd", min_value=0.01, format="%.2f", required=True)
        }
        
        edit_items = st.data_editor(df_items_input, num_rows="dynamic", use_container_width=True, column_config=config, hide_index=True)

        if st.button("✅ Confirmar Recebimento de Toda a Carga", use_container_width=True):
            if not doc_ref:
                st.error("Por favor, preencha o número do Documento/Guia.")
            elif edit_items.empty:
                st.error("Adicione pelo menos um produto na lista abaixo.")
            else:
                try:
                    novas_movs = []
                    fluxo = "ENTRADA" if origem != "SEMED" else "TRANSFERÊNCIA"
                    
                    for _, row in edit_items.iterrows():
                        id_p = df_cat[df_cat['Nome_Produto'] == row['Produto']]['ID_Produto'].values[0]
                        novas_movs.append([
                            f"MOV-{datetime.now().strftime('%y%m%d%H%M%S')}",
                            data_r.strftime('%d/%m/%Y'), id_escola, fluxo, origem, nome_escola, id_p, row['Quantidade'],
                            user_data['email'], doc_ref
                        ])
                    
                    df_to_save = pd.DataFrame(novas_movs, columns=['ID_Movimentacao', 'Data_Hora', 'ID_Escola', 'Tipo_Fluxo', 'Origem', 'Destino', 'ID_Produto', 'Quantidade', 'ID_Usuario', 'Documento_Ref'])
                    
                    if salvar_dados(df_to_save, "db_movimentacoes", modo='append'):
                        st.success(f"Sucesso! {len(df_to_save)} itens foram adicionados ao seu estoque.")
                        st.balloons()
                        st.rerun()
                except Exception as e:
                    st.error(f"Erro ao processar a carga. Verifique se todos os campos da tabela foram preenchidos.")

    # --- 3. REGISTRAR CONSUMO ---
    elif menu == "🍳 Registrar Consumo":
        st.subheader("📉 Baixa de Material Diário")
        df_cat = carregar_dados("db_catalogo")
        
        with st.form("f_consumo_esc", clear_on_submit=True):
            st.write("Informe o que foi utilizado hoje (Merenda, Limpeza, etc).")
            c1, c2 = st.columns(2)
            item_c = c1.selectbox("Produto", df_cat['Nome_Produto'].tolist())
            qtd_c = c1.number_input("Quantidade Utilizada", min_value=0.01)
            obs_c = c2.text_input("Observação (Ex: Cardápio do dia)")
            data_c = c2.date_input("Data do Consumo", datetime.now(), format="DD/MM/YYYY")
            
            if st.form_submit_button("Confirmar Saída", use_container_width=True):
                id_p = df_cat[df_cat['Nome_Produto'] == item_c]['ID_Produto'].values[0]
                nova_saida = pd.DataFrame([[
                    f"SAI-{datetime.now().strftime('%y%m%d%H%M%S')}",
                    data_c.strftime('%d/%m/%Y'), id_escola, "SAÍDA", nome_escola, "CONSUMO INTERNO", id_p, qtd_c,
                    user_data['email'], obs_c
                ]], columns=['ID_Movimentacao', 'Data_Hora', 'ID_Escola', 'Tipo_Fluxo', 'Origem', 'Destino', 'ID_Produto', 'Quantidade', 'ID_Usuario', 'Documento_Ref'])
                
                if salvar_dados(nova_saida, "db_movimentacoes"):
                    st.warning(f"Baixa de {qtd_c} {item_c} registrada.")
                    st.rerun()

    # --- 4. NOVO ITEM NO CATÁLOGO ---
    elif menu == "📂 Novo Item (Agricultura)":
        st.subheader("📂 Cadastrar Novo Produto da Agricultura Familiar")
        st.info("Use esta tela apenas para cadastrar itens que chegaram e NÃO estão na lista do sistema.")
        
        with st.form("f_new_item_escola"):
            c1, c2 = st.columns(2)
            id_p = c1.text_input("ID Sugerido (Ex: AF-001)")
            nm_p = c1.text_input("Nome do Produto")
            cat_p = c2.selectbox("Categoria", ["Alimentação", "Limpeza", "Outros"])
            un_p = c2.selectbox("Unidade", ["Kg", "Maço", "Unid", "Cx", "Pct"])
            
            if st.form_submit_button("Adicionar ao Catálogo da Rede"):
                novo_p = pd.DataFrame([[id_p, nm_p, cat_p, un_p]], columns=['ID_Produto', 'Nome_Produto', 'Categoria', 'Unidade_Medida'])
                if salvar_dados(novo_p, "db_catalogo"):
                    st.success(f"Item '{nm_p}' cadastrado e liberado para recebimento.")
                    st.rerun()

    # --- 5. MEUS RELATÓRIOS (NOVO) ---
    elif menu == "📜 Meus Relatórios":
        st.subheader("📜 Histórico de Movimentação da Escola")
        df_mov = carregar_dados("db_movimentacoes")
        df_cat = carregar_dados("db_catalogo")
        
        # Filtra apenas o que pertence a esta escola
        df_meu = df_mov[df_mov['ID_Escola'] == id_escola].copy()
        
        if not df_meu.empty:
            with st.expander("🔍 Filtros de Consulta"):
                f_tipo = st.multiselect("Filtrar por Tipo", ["ENTRADA", "SAÍDA", "TRANSFERÊNCIA"])
                f_data = st.date_input("Intervalo de Datas", [datetime(2024,1,1), datetime.now()], format="DD/MM/YYYY")
            
            # Aplicação simples de filtros
            if f_tipo:
                df_meu = df_meu[df_meu['Tipo_Fluxo'].isin(f_tipo)]
            
            st.dataframe(df_meu, use_container_width=True, hide_index=True)
            
            csv = df_meu.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 Baixar Meu Histórico (Excel/CSV)", data=csv, file_name=f"Historico_{id_escola}.csv", mime='text/csv', use_container_width=True)
        else:
            st.info("Ainda não existem registros de movimentação para sua escola.")
