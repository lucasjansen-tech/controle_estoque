import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from modules.database import carregar_dados, salvar_dados
from modules.logic import calcular_estoque_atual

def renderizar_escola():
    user_data = st.session_state['usuario_dados']
    id_escola = user_data['id_escola']
    df_esc_ref = carregar_dados("db_escolas")
    df_cat = carregar_dados("db_catalogo")
    nome_escola = next((r['Nome_Escola'] for _, r in df_esc_ref.iterrows() if r['ID_Escola'] == id_escola), "Unidade Escolar")

    st.title(f"🏫 Portal da Escola: {nome_escola}")

    menu = st.sidebar.radio("Navegação", [
        "🏠 Estoque e Gráficos", 
        "📦 Receber Materiais", 
        "✏️ Corrigir Lançamento",
        "🍳 Registrar Uso (Consumo)",
        "📜 Relatórios e Exportação"
    ])

    st.sidebar.divider()
    if st.sidebar.button("🔄 Sincronizar Sistema", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # --- 1. ESTOQUE ATUAL E GRÁFICOS ---
    if menu == "🏠 Estoque e Gráficos":
        st.subheader("📋 Situação Atual do Almoxarifado")
        saldo = calcular_estoque_atual(id_escola)
        
        if not saldo.empty:
            df_f = pd.merge(saldo, df_cat, on='ID_Produto', how='left')
            
            # Gráfico Comparativo de Saldo
            st.markdown("**📊 Nível de Estoque por Produto**")
            st.bar_chart(df_f.set_index('Nome_Produto')['Saldo'])
            
            st.divider()
            # Cards de visualização rápida
            cols = st.columns(3)
            for idx, row in df_f.iterrows():
                with cols[idx % 3].container(border=True):
                    st.markdown(f"### {row['Saldo']}")
                    st.caption(f"{row['Unidade_Medida']}")
                    st.markdown(f"**{row['Nome_Produto']}**")
        else:
            st.info("Nenhum item em estoque no momento.")

    # --- 2. RECEBER MATERIAIS (LOTE DINÂMICO) ---
    elif menu == "📦 Receber Materiais":
        st.subheader("📦 Nova Entrada de Material")
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            origem = c1.selectbox("Origem", ["Agricultura Familiar", "SEMED", "Fornecedor"])
            doc_ref = c2.text_input("Nº Nota/Documento")
            data_r = c3.date_input("Data", datetime.now(), format="DD/MM/YYYY")

        if 'lista_itens' not in st.session_state:
            st.session_state.lista_itens = [{'id': 0, 'prod': None, 'qtd': 0.0}]

        for i, item in enumerate(st.session_state.lista_itens):
            with st.container(border=True):
                col1, col2, col3 = st.columns([3, 1, 0.5])
                st.session_state.lista_itens[i]['prod'] = col1.selectbox(f"Produto {i+1}", [None] + df_cat['Nome_Produto'].tolist(), key=f"p_{item['id']}")
                st.session_state.lista_itens[i]['qtd'] = col2.number_input("Qtd", min_value=0.0, key=f"q_{item['id']}")
                if len(st.session_state.lista_itens) > 1:
                    if col3.button("🗑️", key=f"d_{item['id']}"):
                        st.session_state.lista_itens.pop(i)
                        st.rerun()

        if st.button("➕ Adicionar outro produto"):
            novo_id = st.session_state.lista_itens[-1]['id'] + 1
            st.session_state.lista_itens.append({'id': novo_id, 'prod': None, 'qtd': 0.0})
            st.rerun()

        if st.button("✅ SALVAR RECEBIMENTO", type="primary", use_container_width=True):
            if doc_ref:
                lista_final = []
                for it in st.session_state.lista_itens:
                    if it['prod'] and it['qtd'] > 0:
                        id_p = df_cat[df_cat['Nome_Produto'] == it['prod']]['ID_Produto'].values[0]
                        lista_final.append([f"MOV-{datetime.now().strftime('%H%M%S')}-{it['id']}", data_r.strftime('%d/%m/%Y'), id_escola, "ENTRADA", origem, nome_escola, id_p, it['qtd'], user_data['email'], doc_ref])
                if salvar_dados(pd.DataFrame(lista_final, columns=['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','ID_Usuario','Documento_Ref']), "db_movimentacoes", modo='append'):
                    st.success("Recebimento registrado!")
                    st.session_state.lista_itens = [{'id': 0, 'prod': None, 'qtd': 0.0}]
                    st.rerun()

    # --- 3. CORRIGIR LANÇAMENTO (EXCLUSÃO SEGURA E EDIÇÃO) ---
    elif menu == "✏️ Corrigir Lançamento":
        st.subheader("✏️ Ajustar ou Remover Itens")
        df_mov = carregar_dados("db_movimentacoes")
        minhas = df_mov[df_mov['ID_Escola'] == id_escola].copy()
        
        if not minhas.empty:
            opcoes = sorted((minhas['Documento_Ref'] + " (" + minhas['Data_Hora'] + ")").unique(), reverse=True)
            sel = st.selectbox("Selecione a Nota/Data:", [None] + opcoes)
            
            if sel:
                doc_o = sel.split(" (")[0]
                data_o = sel.split("(")[1].replace(")", "")
                itens_nota = minhas[(minhas['Documento_Ref'] == doc_o) & (minhas['Data_Hora'] == data_o)]
                itens_nota = pd.merge(itens_nota, df_cat[['ID_Produto', 'Nome_Produto']], on='ID_Produto')

                novas_quantidades = {}

                for i, row in itens_nota.iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 1, 1])
                        c1.markdown(f"**Item:** {row['Nome_Produto']}")
                        # Coleta a nova quantidade
                        novas_quantidades[row['ID_Movimentacao']] = c2.number_input("Nova Qtd", value=float(row['Quantidade']), key=f"edit_{row['ID_Movimentacao']}")
                        
                        if c3.button("❌ Excluir Item", key=f"del_item_{row['ID_Movimentacao']}"):
                            df_full = carregar_dados("db_movimentacoes")
                            df_final = df_full[df_full['ID_Movimentacao'] != row['ID_Movimentacao']]
                            if salvar_dados(df_final, "db_movimentacoes", modo='overwrite'):
                                st.warning("Item removido.")
                                st.rerun()

                if st.button("💾 Salvar Alterações de Quantidade", type="primary", use_container_width=True):
                    df_full = carregar_dados("db_movimentacoes")
                    # Atualiza as quantidades no DataFrame principal usando o ID único
                    for id_mov, qtd in novas_quantidades.items():
                        df_full.loc[df_full['ID_Movimentacao'] == id_mov, 'Quantidade'] = qtd
                    
                    if salvar_dados(df_full, "db_movimentacoes", modo='overwrite'):
                        st.success("Quantidades atualizadas com sucesso!")
                        st.rerun()

    # --- 4. REGISTRAR USO (CONSUMO) ---
    elif menu == "🍳 Registrar Uso":
        st.subheader("🍳 Registro de Saída (Consumo Interno)")
        with st.form("f_consumo_unid", clear_on_submit=True):
            col1, col2 = st.columns(2)
            p_c = col1.selectbox("O que foi usado?", df_cat['Nome_Produto'].sort_values().tolist())
            q_c = col1.number_input("Quantidade", min_value=0.01)
            d_c = col2.date_input("Data do Uso", datetime.now(), format="DD/MM/YYYY")
            o_c = col2.text_input("Para que foi usado? (Ex: Merenda)")
            
            if st.form_submit_button("Registrar Saída", use_container_width=True):
                id_p = df_cat[df_cat['Nome_Produto'] == p_c]['ID_Produto'].values[0]
                df_saida = pd.DataFrame([[f"SAI-{datetime.now().strftime('%H%M%S')}", d_c.strftime('%d/%m/%Y'), id_escola, "SAÍDA", nome_escola, "CONSUMO INTERNO", id_p, q_c, user_data['email'], o_c]], 
                                        columns=['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','ID_Usuario','Documento_Ref'])
                if salvar_dados(df_saida, "db_movimentacoes", modo='append'):
                    st.warning(f"Saída de {q_c} {p_c} registrada.")
                    st.rerun()

    # --- 5. RELATÓRIOS E EXPORTAÇÃO ---
    elif menu == "📜 Relatórios e Exportação":
        st.subheader("📜 Histórico e Documentos")
        df_m = carregar_dados("db_movimentacoes")
        df_m = df_m[df_m['ID_Escola'] == id_escola].copy()
        
        if not df_m.empty:
            df_m = pd.merge(df_m, df_cat[['ID_Produto', 'Nome_Produto', 'Unidade_Medida']], on='ID_Produto', how='left')
            
            with st.expander("🔍 Filtros de Relatório"):
                p_r = st.selectbox("Período", ["Mês Atual", "Trimestral", "Anual", "Personalizado"])
                f_t = st.multiselect("Tipo", ["ENTRADA", "SAÍDA"])
            
            # Exibição Agrupada
            for (doc, data), group in df_m.groupby(['Documento_Ref', 'Data_Hora']):
                with st.container(border=True):
                    st.markdown(f"**Documento:** {doc} | **Data:** {data}")
                    st.table(group[['Nome_Produto', 'Quantidade', 'Unidade_Medida', 'Tipo_Fluxo']])

            st.divider()
            # Excel Otimizado (Ordenado logicamente)
            csv = df_m[['Data_Hora', 'Documento_Ref', 'Tipo_Fluxo', 'Nome_Produto', 'Quantidade', 'Unidade_Medida']].to_csv(index=False).encode('utf-8-sig')
            st.download_button("📊 Baixar Excel para Conferência", csv, f"Relatorio_{id_escola}.csv", use_container_width=True)
        else:
            st.info("Nenhuma movimentação encontrada.")
