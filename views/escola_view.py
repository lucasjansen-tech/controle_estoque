import streamlit as st
import pandas as pd
from datetime import datetime
from modules.database import carregar_dados, salvar_dados
from modules.logic import calcular_estoque_atual

def renderizar_escola():
    user_data = st.session_state['usuario_dados']
    id_escola = user_data['id_escola']
    
    # Busca informações da escola
    df_esc_ref = carregar_dados("db_escolas")
    nome_escola = next((r['Nome_Escola'] for _, r in df_esc_ref.iterrows() if r['ID_Escola'] == id_escola), "Unidade Escolar")

    st.title(f"🏫 Portal da Escola: {nome_escola}")
    
    # --- Gestão de Estado para Itens Dinâmicos ---
    if 'lista_recebimento' not in st.session_state:
        st.session_state.lista_recebimento = [{'id': 0, 'produto': None, 'qtd': 0.0}]
    if 'contador_itens' not in st.session_state:
        st.session_state.contador_itens = 1

    # --- Menu Lateral ---
    menu = st.sidebar.radio("O que você precisa fazer?", [
        "🏠 Início / Meu Estoque", 
        "📦 Receber Materiais", 
        "✏️ Corrigir Recebimento",
        "🍳 Registrar Uso (Consumo)",
        "🍎 Cadastrar Novo Item"
    ])

    st.sidebar.divider()
    # Dicas Visuais na Lateral
    if menu == "📦 Receber Materiais":
        st.sidebar.info("""
        **Dicas para Receber:**
        1. Informe os dados da nota/guia.
        2. Clique em **'+ Adicionar Outro Produto'** se chegou mais de uma coisa.
        3. Se errou um item, clique no **'❌'** vermelho ao lado dele.
        """)

    if st.sidebar.button("🔄 Sincronizar Sistema", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # --- 1. INÍCIO / MEU ESTOQUE ---
    if menu == "🏠 Início / Meu Estoque":
        st.subheader("📋 O que temos hoje no estoque?")
        saldo = calcular_estoque_atual(id_escola)
        if not saldo.empty:
            df_cat = carregar_dados("db_catalogo")
            df_final = pd.merge(saldo, df_cat, on='ID_Produto', how='left')
            st.dataframe(df_final[['Nome_Produto', 'Saldo', 'Unidade_Medida', 'Categoria']], use_container_width=True, hide_index=True)
        else:
            st.info("Estoque vazio. Registre uma chegada de materiais.")

    # --- 2. RECEBER MATERIAIS (SEM CARA DE TABELA) ---
    elif menu == "📦 Receber Materiais":
        st.subheader("📦 Registrar Chegada de Carga")
        df_cat = carregar_dados("db_catalogo")
        
        # Cabeçalho do Recebimento
        with st.container(border=True):
            st.markdown("**1. Informações da Entrega**")
            c1, c2, c3 = st.columns(3)
            origem = c1.selectbox("Quem entregou?", ["Agricultura Familiar", "SEMED", "Fornecedor"], help="Origem do material")
            doc_ref = c2.text_input("Nº do Documento / Nota", placeholder="Ex: 123/2026")
            data_r = c3.date_input("Data da entrega", datetime.now(), format="DD/MM/YYYY")

        st.markdown("**2. Itens Recebidos**")
        st.caption("Preencha os produtos e quantidades abaixo:")

        # Lista Dinâmica de Campos (Perde a cara de tabela)
        for i, item in enumerate(st.session_state.lista_recebimento):
            with st.container(border=True):
                col_prod, col_qtd, col_del = st.columns([3, 1, 0.5])
                
                # Seleção do Produto
                st.session_state.lista_recebimento[i]['produto'] = col_prod.selectbox(
                    f"Produto {i+1}", 
                    options=[None] + df_cat['Nome_Produto'].sort_values().tolist(),
                    key=f"prod_{item['id']}",
                    index=0 if item['produto'] is None else df_cat['Nome_Produto'].sort_values().tolist().index(item['produto']) + 1
                )
                
                # Quantidade
                st.session_state.lista_recebimento[i]['qtd'] = col_qtd.number_input(
                    "Qtd", min_value=0.0, step=0.1, key=f"qtd_{item['id']}", format="%.2f"
                )
                
                # Botão Excluir Item (Só aparece se tiver mais de 1)
                if len(st.session_state.lista_recebimento) > 1:
                    if col_del.button("❌", key=f"del_{item['id']}", help="Remover este item"):
                        st.session_state.lista_recebimento.pop(i)
                        st.rerun()

        # Botão Adicionar Novo Item (Bem visível)
        if st.button("➕ Adicionar Outro Produto", type="secondary"):
            st.session_state.lista_recebimento.append({'id': st.session_state.contador_itens, 'produto': None, 'qtd': 0.0})
            st.session_state.contador_itens += 1
            st.rerun()

        st.divider()
        if st.button("✅ FINALIZAR E SALVAR RECEBIMENTO", type="primary", use_container_width=True):
            if not doc_ref:
                st.error("Preencha o número do documento!")
            else:
                lista_final = []
                fluxo = "ENTRADA" if origem != "SEMED" else "TRANSFERÊNCIA"
                
                for item in st.session_state.lista_recebimento:
                    if item['produto'] and item['qtd'] > 0:
                        id_p = df_cat[df_cat['Nome_Produto'] == item['produto']]['ID_Produto'].values[0]
                        lista_final.append([
                            f"MOV-{datetime.now().strftime('%y%m%d%H%M%S')}",
                            data_r.strftime('%d/%m/%Y'), id_escola, fluxo, origem, nome_escola, id_p, item['qtd'],
                            user_data['email'], doc_ref
                        ])
                
                if lista_final:
                    df_save = pd.DataFrame(lista_final, columns=['ID_Movimentacao', 'Data_Hora', 'ID_Escola', 'Tipo_Fluxo', 'Origem', 'Destino', 'ID_Produto', 'Quantidade', 'ID_Usuario', 'Documento_Ref'])
                    if salvar_dados(df_save, "db_movimentacoes"):
                        st.success("Recebimento salvo com sucesso!")
                        st.session_state.lista_recebimento = [{'id': 0, 'produto': None, 'qtd': 0.0}]
                        st.rerun()
                else:
                    st.warning("Adicione produtos válidos e quantidades maiores que zero.")

    # --- 3. CORRIGIR RECEBIMENTO (NOVA FUNCIONALIDADE) ---
    elif menu == "✏️ Corrigir Recebimento":
        st.subheader("✏️ Alterar ou Corrigir Lançamentos")
        st.markdown("Busque pelo número do documento para editar os dados.")
        
        df_mov = carregar_dados("db_movimentacoes")
        minhas_movs = df_mov[df_mov['ID_Escola'] == id_escola]
        
        docs_disponiveis = minhas_movs['Documento_Ref'].unique().tolist()
        doc_para_editar = st.selectbox("Escolha o Documento/Nota:", [None] + docs_disponiveis)
        
        if doc_para_editar:
            dados_edicao = minhas_movs[minhas_movs['Documento_Ref'] == doc_para_editar].copy()
            st.info("Altere as quantidades diretamente na tabela abaixo e clique em Salvar.")
            
            # Editor para correção rápida
            df_editado = st.data_editor(dados_edicao, use_container_width=True, hide_index=True,
                                      disabled=['ID_Movimentacao', 'Data_Hora', 'ID_Escola', 'ID_Usuario'])
            
            if st.button("💾 Salvar Correções"):
                # Remove os dados antigos do documento e insere os novos
                df_completo = carregar_dados("db_movimentacoes")
                df_sem_este_doc = df_completo[df_completo['Documento_Ref'] != doc_para_editar]
                df_final = pd.concat([df_sem_este_doc, df_editado])
                
                if salvar_dados(df_final, "db_movimentacoes", modo='overwrite'):
                    st.success("Documento corrigido com sucesso!")
                    st.rerun()

    # --- RESTANTE DAS FUNÇÕES (Consumo e Novo Item) ---
    elif menu == "🍳 Registrar Uso (Consumo)":
        st.subheader("🍳 Uso Diário de Materiais")
        df_cat = carregar_dados("db_catalogo")
        with st.form("f_uso"):
            c1, c2 = st.columns(2)
            it = c1.selectbox("Produto", df_cat['Nome_Produto'].tolist())
            qt = c1.number_input("Qtd usada", min_value=0.01)
            obs = c2.text_input("Observação (Ex: Almoço)")
            dt = c2.date_input("Data", datetime.now(), format="DD/MM/YYYY")
            if st.form_submit_button("Confirmar Saída", use_container_width=True):
                id_p = df_cat[df_cat['Nome_Produto'] == it]['ID_Produto'].values[0]
                nova_s = pd.DataFrame([[f"SAI-{datetime.now().strftime('%y%m%d%H%M%S')}", dt.strftime('%d/%m/%Y'), id_escola, "SAÍDA", nome_escola, "CONSUMO", id_p, qt, user_data['email'], obs]], 
                                    columns=['ID_Movimentacao', 'Data_Hora', 'ID_Escola', 'Tipo_Fluxo', 'Origem', 'Destino', 'ID_Produto', 'Quantidade', 'ID_Usuario', 'Documento_Ref'])
                salvar_dados(nova_s, "db_movimentacoes")
                st.rerun()

    elif menu == "🍎 Cadastrar Novo Item":
        st.subheader("🍎 Novo Item da Agricultura Familiar")
        with st.form("f_novo"):
            id_p = st.text_input("ID do Produto (Ex: AF-MELANCIA)")
            nm_p = st.text_input("Nome do Produto")
            un_p = st.selectbox("Unidade", ["Kg", "Unid", "Maço", "Pct"])
            if st.form_submit_button("Cadastrar no Sistema"):
                salvar_dados(pd.DataFrame([[id_p, nm_p, "Agricultura Familiar", un_p]], columns=['ID_Produto', 'Nome_Produto', 'Categoria', 'Unidade_Medida']), "db_catalogo")
                st.rerun()

    elif menu == "📜 Relatórios da Escola":
        st.subheader("📜 Histórico de Movimentações")
        df_mov = carregar_dados("db_movimentacoes")
        df_meu = df_mov[df_mov['ID_Escola'] == id_escola]
        st.dataframe(df_meu, use_container_width=True, hide_index=True)
        st.download_button("📥 Baixar Relatório", df_meu.to_csv(index=False).encode('utf-8-sig'), "relatorio.csv", "text/csv", use_container_width=True)
