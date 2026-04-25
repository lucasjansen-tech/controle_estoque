import streamlit as st
import pandas as pd
from datetime import datetime
from modules.database import carregar_dados, salvar_dados
from modules.logic import calcular_estoque_atual

def renderizar_escola():
    # Contexto do usuário logado
    user_data = st.session_state['usuario_dados']
    id_escola = user_data['id_escola']
    
    # Busca informações da escola para o cabeçalho
    df_esc_ref = carregar_dados("db_escolas")
    nome_escola = "Unidade Escolar"
    if not df_esc_ref.empty:
        info = df_esc_ref[df_esc_ref['ID_Escola'] == id_escola]
        if not info.empty:
            nome_escola = info.iloc[0]['Nome_Escola']

    st.title(f"🏫 Portal da Escola: {nome_escola}")
    st.caption(f"Operador: {user_data['email']} | Unidade: {id_escola}")

    # Menu Lateral com Dicas Amigáveis
    menu = st.sidebar.radio("O que deseja fazer hoje?", [
        "📊 Ver meu Estoque", 
        "📥 Receber Novos Materiais", 
        "🍳 Registrar Uso Diário",
        "📂 Cadastrar Produto Novo",
        "📜 Relatórios da Escola"
    ])

    st.sidebar.divider()
    
    # Instruções dinâmicas na lateral para ajudar quem não tem perícia técnica
    if menu == "📥 Receber Novos Materiais":
        st.sidebar.info("""
        **💡 Como registrar a entrega:**
        1. Preencha a **Origem** e o **Nº do Documento**.
        2. Na lista abaixo, clique no **(+)** para adicionar produtos.
        3. Escolha o produto e coloque a **Quantidade**.
        4. Clique no botão verde final para salvar.
        """)
    
    if st.sidebar.button("🔄 Atualizar Informações", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # --- 1. PAINEL DE ESTOQUE ---
    if menu == "📊 Ver meu Estoque":
        st.subheader("📋 Materiais Disponíveis na Escola")
        saldo = calcular_estoque_atual(id_escola)
        
        if not saldo.empty:
            df_cat = carregar_dados("db_catalogo")
            df_final = pd.merge(saldo, df_cat, on='ID_Produto', how='left')
            
            st.write("Estes são os produtos que você tem em mãos no momento:")
            st.dataframe(df_final[['Nome_Produto', 'Saldo', 'Unidade_Medida', 'Categoria']], 
                         use_container_width=True, hide_index=True)
        else:
            st.info("Sua escola ainda não possui itens no estoque. Registre uma entrega para começar.")

    # --- 2. RECEBIMENTO EM LOTE (RESOLUÇÃO DE ERROS) ---
    elif menu == "📥 Receber Novos Materiais":
        st.subheader("📥 Registro de Chegada de Materiais")
        st.markdown("Use esta tela quando chegar um caminhão ou entrega com vários itens.")
        
        df_cat = carregar_dados("db_catalogo")
        
        # Seção de Dados Gerais da Entrega
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            origem = c1.selectbox("De onde veio?", ["Agricultura Familiar", "SEMED", "Outros"], help="Selecione quem entregou o material.")
            doc_ref = c2.text_input("Nº da Guia ou Nota", help="Número que vem no papel da entrega.")
            data_r = c3.date_input("Data que chegou", datetime.now(), format="DD/MM/YYYY")

        st.write("📝 **Lista de Produtos que chegaram:**")
        
        # Estrutura para entrada de dados múltipla
        # Criamos um DataFrame vazio com as colunas corretas para o editor
        if 'df_recebimento' not in st.session_state:
            st.session_state.df_recebimento = pd.DataFrame(columns=['Produto', 'Quantidade'])

        # Configuração das colunas do editor para ser intuitivo
        config_colunas = {
            "Produto": st.column_config.SelectboxColumn(
                "Escolha o Produto", 
                options=df_cat['Nome_Produto'].sort_values().tolist(),
                required=True,
                width="large"
            ),
            "Quantidade": st.column_config.NumberColumn(
                "Quantidade", 
                min_value=0.01, 
                format="%.2f", 
                required=True,
                help="Use a vírgula para números quebrados (Ex: 10,50)"
            )
        }
        
        # O Editor de Dados (Onde o erro costuma ocorrer)
        itens_recebidos = st.data_editor(
            st.session_state.df_recebimento, 
            num_rows="dynamic", 
            use_container_width=True, 
            column_config=config_colunas,
            hide_index=True,
            key="editor_recebimento"
        )

        if st.button("✅ Confirmar Recebimento de Todos os Itens", use_container_width=True, type="primary"):
            if not doc_ref:
                st.error("⚠️ Você esqueceu de colocar o Número da Guia ou Nota!")
            elif itens_recebidos.empty or itens_recebidos['Produto'].isnull().all():
                st.error("⚠️ A lista de produtos está vazia. Adicione pelo menos um item.")
            else:
                try:
                    lista_para_salvar = []
                    tipo_fluxo = "ENTRADA" if origem != "SEMED" else "TRANSFERÊNCIA"
                    
                    # Processa cada linha preenchida na tabela
                    for _, linha in itens_recebidos.iterrows():
                        if pd.notnull(linha['Produto']) and linha['Quantidade'] > 0:
                            # Busca o ID do produto pelo nome selecionado
                            id_p = df_cat[df_cat['Nome_Produto'] == linha['Produto']]['ID_Produto'].values[0]
                            
                            lista_para_salvar.append([
                                f"MOV-{datetime.now().strftime('%y%m%d%H%M%S')}", # ID Único
                                data_r.strftime('%d/%m/%Y'), 
                                id_escola, 
                                tipo_fluxo, 
                                origem, 
                                nome_escola, 
                                id_p, 
                                linha['Quantidade'],
                                user_data['email'], 
                                doc_ref
                            ])
                    
                    if lista_para_salvar:
                        df_final_mov = pd.DataFrame(lista_para_salvar, columns=[
                            'ID_Movimentacao', 'Data_Hora', 'ID_Escola', 'Tipo_Fluxo', 
                            'Origem', 'Destino', 'ID_Produto', 'Quantidade', 'ID_Usuario', 'Documento_Ref'
                        ])
                        
                        if salvar_dados(df_final_mov, "db_movimentacoes", modo='append'):
                            st.success(f"📦 Sucesso! {len(lista_para_salvar)} itens foram registrados no estoque.")
                            st.balloons()
                            # Limpa o editor após o sucesso
                            del st.session_state.df_recebimento
                            st.rerun()
                except Exception as e:
                    st.error(f"❌ Erro ao processar: Certifique-se de que escolheu o produto e a quantidade em todas as linhas.")

    # --- 3. REGISTRAR USO DIÁRIO ---
    elif menu == "🍳 Registrar Uso Diário":
        st.subheader("🍳 Registro de Consumo (Merenda/Limpeza)")
        df_cat = carregar_dados("db_catalogo")
        
        with st.form("f_uso_diario", clear_on_submit=True):
            st.write("O que foi usado hoje na escola?")
            col_u1, col_u2 = st.columns(2)
            item_u = col_u1.selectbox("Produto", df_cat['Nome_Produto'].tolist())
            qtd_u = col_u1.number_input("Quantidade Utilizada", min_value=0.01)
            obs_u = col_u2.text_input("Para que foi usado? (Ex: Merenda, Faxina)")
            data_u = col_u2.date_input("Data do Uso", datetime.now(), format="DD/MM/YYYY")
            
            if st.form_submit_button("Registrar Saída do Estoque", use_container_width=True):
                id_p_u = df_cat[df_cat['Nome_Produto'] == item_u]['ID_Produto'].values[0]
                nova_saida = pd.DataFrame([[
                    f"SAI-{datetime.now().strftime('%y%m%d%H%M%S')}",
                    data_u.strftime('%d/%m/%Y'), id_escola, "SAÍDA", nome_escola, "CONSUMO INTERNO", id_p_u, qtd_u,
                    user_data['email'], obs_u
                ]], columns=['ID_Movimentacao', 'Data_Hora', 'ID_Escola', 'Tipo_Fluxo', 'Origem', 'Destino', 'ID_Produto', 'Quantidade', 'ID_Usuario', 'Documento_Ref'])
                
                if salvar_dados(nova_saida, "db_movimentacoes"):
                    st.warning(f"Baixa realizada: {qtd_u} de {item_u} saiu do estoque.")
                    st.rerun()

    # --- 4. RELATÓRIOS DA ESCOLA ---
    elif menu == "📜 Relatórios da Escola":
        st.subheader("📜 Histórico de Entradas e Saídas")
        df_mov = carregar_dados("db_movimentacoes")
        
        # Filtra apenas os dados desta escola específica
        meu_historico = df_mov[df_mov['ID_Escola'] == id_escola].copy()
        
        if not meu_historico.empty:
            st.write("Veja tudo o que aconteceu no seu estoque:")
            
            with st.expander("🔍 Filtrar meu histórico"):
                tipo_f = st.multiselect("Filtrar por tipo", ["ENTRADA", "SAÍDA", "TRANSFERÊNCIA"])
                if tipo_f:
                    meu_historico = meu_historico[meu_historico['Tipo_Fluxo'].isin(tipo_f)]
            
            st.dataframe(meu_historico, use_container_width=True, hide_index=True)
            
            # Opção de Download
            csv = meu_historico.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 Baixar meu relatório (Excel)", data=csv, file_name=f"Estoque_{nome_escola}.csv", mime='text/csv', use_container_width=True)
        else:
            st.info("Sua escola ainda não possui histórico de movimentações.")
