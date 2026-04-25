import streamlit as st
import pandas as pd
from datetime import datetime
from modules.database import carregar_dados, salvar_dados
from modules.logic import calcular_estoque_atual

def renderizar_escola():
    user_data = st.session_state['usuario_dados']
    id_escola = user_data['id_escola']
    
    # Busca informações da unidade e catálogo
    df_esc_ref = carregar_dados("db_escolas")
    df_cat = carregar_dados("db_catalogo")
    nome_escola = next((r['Nome_Escola'] for _, r in df_esc_ref.iterrows() if r['ID_Escola'] == id_escola), "Unidade Escolar")

    st.title(f"🏫 Portal da Escola: {nome_escola}")
    
    # --- Gestão de Estado para Itens Dinâmicos (Recebimento) ---
    if 'lista_recebimento' not in st.session_state:
        st.session_state.lista_recebimento = [{'id': 0, 'produto': None, 'qtd': 0.0}]
    if 'contador_itens' not in st.session_state:
        st.session_state.contador_itens = 1

    # --- Menu Lateral ---
    menu = st.sidebar.radio("O que você precisa fazer?", [
        "🏠 Meu Estoque Atual", 
        "📦 Receber Novos Materiais", 
        "✏️ Corrigir Lançamento",
        "🍳 Registrar Uso (Consumo)",
        "📜 Relatórios Detalhados"
    ])

    st.sidebar.divider()
    if st.sidebar.button("🔄 Sincronizar Sistema", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # --- 1. INÍCIO / MEU ESTOQUE ---
    if menu == "🏠 Meu Estoque Atual":
        st.subheader("📋 Saldo de Materiais na Escola")
        saldo = calcular_estoque_atual(id_escola)
        if not saldo.empty:
            df_final = pd.merge(saldo, df_cat, on='ID_Produto', how='left')
            st.write("Estes são os itens disponíveis para uso imediato:")
            
            # Interface de cards para o estoque (Fim da cara de Excel)
            for _, row in df_final.iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 1, 1])
                    c1.markdown(f"**{row['Nome_Produto']}**")
                    c2.markdown(f"Saldo: `{row['Saldo']}` {row['Unidade_Medida']}")
                    c3.markdown(f"*{row['Categoria']}*")
        else:
            st.info("O estoque está vazio. Registre uma chegada de materiais.")

    # --- 2. RECEBER MATERIAIS (LOTE DINÂMICO) ---
    elif menu == "📦 Receber Novos Materiais":
        st.subheader("📦 Registrar Chegada de Carga")
        
        with st.container(border=True):
            st.markdown("**1. Informações da Nota/Guia**")
            c1, c2, c3 = st.columns(3)
            origem = c1.selectbox("Quem entregou?", ["Agricultura Familiar", "SEMED", "Fornecedor"])
            doc_ref = c2.text_input("Nº da Nota / Documento")
            data_r = c3.date_input("Data da entrega", datetime.now(), format="DD/MM/YYYY")

        st.markdown("**2. Produtos Recebidos**")
        for i, item in enumerate(st.session_state.lista_recebimento):
            with st.container(border=True):
                col_p, col_q, col_d = st.columns([3, 1, 0.5])
                st.session_state.lista_recebimento[i]['produto'] = col_p.selectbox(
                    f"Produto {i+1}", options=[None] + df_cat['Nome_Produto'].sort_values().tolist(),
                    key=f"prod_{item['id']}"
                )
                st.session_state.lista_recebimento[i]['qtd'] = col_q.number_input(
                    "Qtd", min_value=0.0, step=0.1, key=f"qtd_{item['id']}"
                )
                if len(st.session_state.lista_recebimento) > 1:
                    if col_d.button("❌", key=f"del_{item['id']}"):
                        st.session_state.lista_recebimento.pop(i)
                        st.rerun()

        if st.button("➕ Adicionar Outro Produto", type="secondary"):
            st.session_state.lista_recebimento.append({'id': st.session_state.contador_itens, 'produto': None, 'qtd': 0.0})
            st.session_state.contador_itens += 1
            st.rerun()

        st.divider()
        if st.button("✅ SALVAR RECEBIMENTO", type="primary", use_container_width=True):
            if not doc_ref:
                st.error("Informe o número do documento!")
            else:
                lista_final = []
                for it in st.session_state.lista_recebimento:
                    if it['produto'] and it['qtd'] > 0:
                        id_p = df_cat[df_cat['Nome_Produto'] == it['produto']]['ID_Produto'].values[0]
                        lista_final.append([
                            f"MOV-{datetime.now().strftime('%y%m%d%H%M%S')}-{it['id']}",
                            data_r.strftime('%d/%m/%Y'), id_escola, "ENTRADA" if origem != "SEMED" else "TRANSFERÊNCIA",
                            origem, nome_escola, id_p, it['qtd'], user_data['email'], doc_ref
                        ])
                if lista_final:
                    df_save = pd.DataFrame(lista_final, columns=['ID_Movimentacao', 'Data_Hora', 'ID_Escola', 'Tipo_Fluxo', 'Origem', 'Destino', 'ID_Produto', 'Quantidade', 'ID_Usuario', 'Documento_Ref'])
                    if salvar_dados(df_save, "db_movimentacoes", modo='append'):
                        st.success("Recebimento registrado!")
                        st.session_state.lista_recebimento = [{'id': 0, 'produto': None, 'qtd': 0.0}]
                        st.rerun()

    # --- 3. CORRIGIR LANÇAMENTO (FIM DA CARA DE EXCEL E FIX PRODUTO) ---
    elif menu == "✏️ Corrigir Lançamento":
        st.subheader("✏️ Alterar Dados de uma Nota")
        df_mov = carregar_dados("db_movimentacoes")
        minhas_movs = df_mov[df_mov['ID_Escola'] == id_escola].copy()
        
        if not minhas_movs.empty:
            # Busca nomes dos produtos para exibição
            minhas_movs = pd.merge(minhas_movs, df_cat[['ID_Produto', 'Nome_Produto']], on='ID_Produto', how='left')
            
            # Filtro inteligente por Nota e Data
            minhas_movs['Label_Busca'] = minhas_movs['Documento_Ref'] + " (Data: " + minhas_movs['Data_Hora'] + ")"
            opcoes_notas = sorted(minhas_movs['Label_Busca'].unique().tolist(), reverse=True)
            
            nota_selecionada = st.selectbox("Selecione a Nota que deseja corrigir:", [None] + opcoes_notas)
            
            if nota_selecionada:
                doc_orig = nota_selecionada.split(" (Data:")[0]
                data_orig = nota_selecionada.split("(Data: ")[1].replace(")", "")
                
                itens_edicao = minhas_movs[(minhas_movs['Documento_Ref'] == doc_orig) & 
                                          (minhas_movs['Data_Hora'] == data_orig)].to_dict('records')
                
                st.warning(f"Editando a nota **{doc_orig}** de **{data_orig}**.")
                
                novos_dados = []
                for i, item in enumerate(itens_edicao):
                    with st.container(border=True):
                        st.markdown(f"**Produto:** {item['Nome_Produto']}")
                        c1, c2 = st.columns(2)
                        nova_qtd = c1.number_input("Quantidade", value=float(item['Quantidade']), key=f"edit_q_{i}")
                        nova_orig = c2.selectbox("Origem", ["Agricultura Familiar", "SEMED", "Fornecedor"], 
                                                index=["Agricultura Familiar", "SEMED", "Fornecedor"].index(item['Origem']),
                                                key=f"edit_o_{i}")
                        
                        # Mantém os dados originais e atualiza os editados
                        item_atualizado = item.copy()
                        item_atualizado['Quantidade'] = nova_qtd
                        item_atualizado['Origem'] = nova_orig
                        # Remove a coluna temporária do merge antes de salvar
                        item_atualizado.pop('Nome_Produto', None)
                        item_atualizado.pop('Label_Busca', None)
                        novos_dados.append(item_atualizado)
                
                if st.button("💾 Salvar Alterações na Nota", type="primary", use_container_width=True):
                    df_full = carregar_dados("db_movimentacoes")
                    # Filtra para remover a nota antiga e inserir a nova
                    mask = (df_full['Documento_Ref'] == doc_orig) & (df_full['Data_Hora'] == data_orig) & (df_full['ID_Escola'] == id_escola)
                    df_limpo = df_full[~mask]
                    df_final = pd.concat([df_limpo, pd.DataFrame(novos_dados)])
                    
                    if salvar_dados(df_final, "db_movimentacoes", modo='overwrite'):
                        st.success("Nota corrigida com sucesso!")
                        st.rerun()
        else:
            st.info("Não há lançamentos para corrigir.")

    # --- 5. RELATÓRIOS DETALHADOS (FILTROS E CARDS) ---
    elif menu == "📜 Relatórios Detalhados":
        st.subheader("📜 Histórico de Movimentação")
        df_mov = carregar_dados("db_movimentacoes")
        df_meu = df_mov[df_mov['ID_Escola'] == id_escola].copy()
        
        if not df_meu.empty:
            df_meu = pd.merge(df_meu, df_cat[['ID_Produto', 'Nome_Produto']], on='ID_Produto', how='left')
            
            with st.container(border=True):
                st.markdown("**🔍 Filtros de Pesquisa**")
                c1, c2, c3 = st.columns(3)
                f_tipo = c1.multiselect("Tipo", ["ENTRADA", "SAÍDA", "TRANSFERÊNCIA"])
                f_prod = c2.multiselect("Produto", df_cat['Nome_Produto'].unique())
                data_range = c3.date_input("Período", [datetime(2024,1,1), datetime.now()], format="DD/MM/YYYY")

            # Lógica de Filtro
            df_meu['DT'] = pd.to_datetime(df_meu['Data_Hora'], dayfirst=True, errors='coerce')
            if f_tipo: df_meu = df_meu[df_meu['Tipo_Fluxo'].isin(f_tipo)]
            if f_prod: df_meu = df_meu[df_meu['Nome_Produto'].isin(f_prod)]
            if len(data_range) == 2:
                df_meu = df_meu[(df_meu['DT'].dt.date >= data_range[0]) & (df_meu['DT'].dt.date <= data_range[1])]

            st.write(f"Encontrados **{len(df_meu)}** registros:")
            
            # Exibição em lista formatada (Fim da cara de Excel)
            for _, r in df_meu.sort_values('DT', ascending=False).iterrows():
                cor = "green" if r['Tipo_Fluxo'] == "ENTRADA" else "blue" if r['Tipo_Fluxo'] == "TRANSFERÊNCIA" else "red"
                with st.container(border=True):
                    st.markdown(f":{cor}[**{r['Tipo_Fluxo']}**] | Data: `{r['Data_Hora']}` | Doc: `{r['Documento_Ref']}`")
                    st.write(f"**Item:** {r['Nome_Produto']} | **Quantidade:** {r['Quantidade']} | **Origem:** {r['Origem']}")
            
            st.divider()
            st.download_button("📥 Baixar Relatório Completo", df_meu.to_csv(index=False).encode('utf-8-sig'), 
                               f"Relatorio_{id_escola}.csv", use_container_width=True)
