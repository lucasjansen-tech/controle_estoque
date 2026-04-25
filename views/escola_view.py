import streamlit as st
import pandas as pd
from datetime import datetime
from modules.database import carregar_dados, salvar_dados
from modules.logic import calcular_estoque_atual

def renderizar_escola():
    user_data = st.session_state['usuario_dados']
    id_escola = user_data['id_escola']
    
    # Busca informações básicas
    df_esc_ref = carregar_dados("db_escolas")
    df_cat = carregar_dados("db_catalogo")
    nome_escola = next((r['Nome_Escola'] for _, r in df_esc_ref.iterrows() if r['ID_Escola'] == id_escola), "Unidade Escolar")

    st.title(f"🏫 Portal da Escola: {nome_escola}")
    
    # Estados para Recebimento Dinâmico
    if 'lista_recebimento' not in st.session_state:
        st.session_state.lista_recebimento = [{'id': 0, 'produto': None, 'qtd': 0.0}]
    if 'contador_itens' not in st.session_state:
        st.session_state.contador_itens = 1

    menu = st.sidebar.radio("O que deseja fazer?", [
        "🏠 Meu Estoque Atual", 
        "📦 Receber Materiais", 
        "✏️ Corrigir Lançamento",
        "🍳 Registrar Uso (Consumo)",
        "📜 Relatórios da Unidade"
    ])

    st.sidebar.divider()
    if st.sidebar.button("🔄 Sincronizar Dados", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # --- 1. MEU ESTOQUE ---
    if menu == "🏠 Meu Estoque Atual":
        st.subheader("📋 Saldo de Materiais")
        saldo = calcular_estoque_atual(id_escola)
        if not saldo.empty:
            df_f = pd.merge(saldo, df_cat, on='ID_Produto', how='left')
            for _, row in df_f.iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    c1.markdown(f"**{row['Nome_Produto']}**")
                    c2.markdown(f"Saldo: `{row['Saldo']}` {row['Unidade_Medida']}")
        else:
            st.info("Estoque vazio.")

    # --- 2. RECEBER MATERIAIS ---
    elif menu == "📦 Receber Materiais":
        st.subheader("📦 Registrar Chegada de Carga")
        
        with st.container(border=True):
            st.markdown("**1. Dados da Entrega**")
            c1, c2, c3 = st.columns(3)
            origem = c1.selectbox("Origem", ["Agricultura Familiar", "SEMED", "Fornecedor"])
            doc_ref = c2.text_input("Nº Nota/Documento")
            data_r = c3.date_input("Data", datetime.now(), format="DD/MM/YYYY")

        st.markdown("**2. Itens da Carga**")
        for i, item in enumerate(st.session_state.lista_recebimento):
            with st.container(border=True):
                cp, cq, cd = st.columns([3, 1, 0.5])
                st.session_state.lista_recebimento[i]['produto'] = cp.selectbox(f"Produto {i+1}", [None] + df_cat['Nome_Produto'].sort_values().tolist(), key=f"rec_p_{item['id']}")
                st.session_state.lista_recebimento[i]['qtd'] = cq.number_input("Qtd", min_value=0.0, key=f"rec_q_{item['id']}")
                if len(st.session_state.lista_recebimento) > 1:
                    if cd.button("❌", key=f"rec_d_{item['id']}"):
                        st.session_state.lista_recebimento.pop(i)
                        st.rerun()

        if st.button("➕ Adicionar outro produto"):
            st.session_state.lista_recebimento.append({'id': st.session_state.contador_itens, 'produto': None, 'qtd': 0.0})
            st.session_state.contador_itens += 1
            st.rerun()

        if st.button("✅ SALVAR TUDO", type="primary", use_container_width=True):
            if doc_ref:
                lista_s = []
                for it in st.session_state.lista_recebimento:
                    if it['produto'] and it['qtd'] > 0:
                        id_p = df_cat[df_cat['Nome_Produto'] == it['produto']]['ID_Produto'].values[0]
                        lista_s.append([f"MOV-{datetime.now().strftime('%y%m%d%H%M%S')}-{it['id']}", data_r.strftime('%d/%m/%Y'), id_escola, "ENTRADA" if origem != "SEMED" else "TRANSFERÊNCIA", origem, nome_escola, id_p, it['qtd'], user_data['email'], doc_ref])
                if lista_s:
                    if salvar_dados(pd.DataFrame(lista_s, columns=['ID_Movimentacao', 'Data_Hora', 'ID_Escola', 'Tipo_Fluxo', 'Origem', 'Destino', 'ID_Produto', 'Quantidade', 'ID_Usuario', 'Documento_Ref']), "db_movimentacoes", modo='append'):
                        st.success("Salvo!")
                        st.session_state.lista_recebimento = [{'id': 0, 'produto': None, 'qtd': 0.0}]
                        st.rerun()

    # --- 3. CORRIGIR LANÇAMENTO (COM OPÇÃO DE EXCLUSÃO) ---
    elif menu == "✏️ Corrigir Lançamento":
        st.subheader("✏️ Ajustar ou Excluir Lançamentos")
        df_mov = carregar_dados("db_movimentacoes")
        minhas = df_mov[df_mov['ID_Escola'] == id_escola].copy()
        
        if not minhas.empty:
            minhas['Busca'] = minhas['Documento_Ref'] + " (" + minhas['Data_Hora'] + ")"
            nota_sel = st.selectbox("Escolha a Nota/Data:", [None] + sorted(minhas['Busca'].unique().tolist(), reverse=True))
            
            if nota_sel:
                doc_o = nota_sel.split(" (")[0]
                data_o = nota_sel.split("(")[1].replace(")", "")
                
                # Carrega itens da nota com nomes reais
                itens_nota = minhas[(minhas['Documento_Ref'] == doc_o) & (minhas['Data_Hora'] == data_o)]
                itens_nota = pd.merge(itens_nota, df_cat[['ID_Produto', 'Nome_Produto']], on='ID_Produto', how='left')
                
                itens_editados = []
                excluidos = []

                for i, row in itens_nota.iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 1, 1])
                        c1.markdown(f"**Item:** {row['Nome_Produto']}")
                        nova_q = c2.number_input("Qtd", value=float(row['Quantidade']), key=f"ed_q_{i}")
                        
                        # BOTÃO DE EXCLUSÃO DE ITEM ESPECÍFICO
                        if c3.button("🗑️ Excluir Item", key=f"ed_d_{i}", help="Remove este produto desta nota permanentemente"):
                            excluidos.append(row['ID_Movimentacao'])
                            st.toast(f"Item {row['Nome_Produto']} marcado para exclusão.")
                        
                        item_up = row.to_dict()
                        item_up['Quantidade'] = nova_q
                        itens_editados.append(item_up)

                if st.button("💾 Salvar Alterações", type="primary", use_container_width=True):
                    df_full = carregar_dados("db_movimentacoes")
                    # Remove os itens originais e os marcados para exclusão
                    ids_para_remover = itens_nota['ID_Movimentacao'].tolist()
                    df_limpo = df_full[~df_full['ID_Movimentacao'].isin(ids_para_remover)]
                    
                    # Filtra os itens editados removendo os que o usuário clicou em 'Excluir'
                    df_novos = pd.DataFrame(itens_editados)
                    df_novos = df_novos[~df_novos['ID_Movimentacao'].isin(excluidos)]
                    
                    # Limpeza de colunas temporárias
                    df_novos = df_novos.drop(columns=['Nome_Produto', 'Busca'], errors='ignore')
                    
                    df_final = pd.concat([df_limpo, df_novos])
                    if salvar_dados(df_final, "db_movimentacoes", modo='overwrite'):
                        st.success("Nota atualizada!")
                        st.rerun()
        else:
            st.info("Nada para corrigir.")

    # --- 4. REGISTRAR USO (CONSUMO) - RESTAURADO ---
    elif menu == "🍳 Registrar Uso (Consumo)":
        st.subheader("🍳 Registro de Saída (Consumo Interno)")
        st.markdown("Use esta tela para dar baixa no que foi consumido na cozinha ou limpeza.")
        
        with st.form("f_consumo_novo", clear_on_submit=True):
            col1, col2 = st.columns(2)
            prod_c = col1.selectbox("O que foi usado?", df_cat['Nome_Produto'].sort_values().tolist())
            qtd_c = col1.number_input("Quantidade", min_value=0.01)
            data_c = col2.date_input("Data do Uso", datetime.now(), format="DD/MM/YYYY")
            obs_c = col2.text_input("Observação", placeholder="Ex: Merenda Fundamental I")
            
            if st.form_submit_button("Confirmar Saída", use_container_width=True):
                id_p = df_cat[df_cat['Nome_Produto'] == prod_c]['ID_Produto'].values[0]
                df_saida = pd.DataFrame([[f"SAI-{datetime.now().strftime('%y%m%d%H%M%S')}", data_c.strftime('%d/%m/%Y'), id_escola, "SAÍDA", nome_escola, "CONSUMO INTERNO", id_p, qtd_c, user_data['email'], obs_c]], 
                                        columns=['ID_Movimentacao', 'Data_Hora', 'ID_Escola', 'Tipo_Fluxo', 'Origem', 'Destino', 'ID_Produto', 'Quantidade', 'ID_Usuario', 'Documento_Ref'])
                if salvar_dados(df_saida, "db_movimentacoes", modo='append'):
                    st.warning(f"Baixa de {qtd_c} {prod_c} realizada.")
                    st.rerun()

    # --- 5. RELATÓRIOS (AGRUPADOS POR NOTA) ---
    elif menu == "📜 Relatórios da Unidade":
        st.subheader("📜 Histórico de Movimentações Agrupado")
        df_m = carregar_dados("db_movimentacoes")
        df_m = df_m[df_m['ID_Escola'] == id_escola].copy()
        
        if not df_m.empty:
            df_m = pd.merge(df_m, df_cat[['ID_Produto', 'Nome_Produto']], on='ID_Produto', how='left')
            
            # Filtros
            with st.expander("🔍 Filtros"):
                f_t = st.multiselect("Tipo", ["ENTRADA", "SAÍDA", "TRANSFERÊNCIA"])
                f_d = st.date_input("Período", [datetime(2024,1,1), datetime.now()])
            
            df_m['DT'] = pd.to_datetime(df_m['Data_Hora'], dayfirst=True, errors='coerce')
            if f_t: df_m = df_m[df_m['Tipo_Fluxo'].isin(f_t)]
            if len(f_d) == 2: df_m = df_m[(df_m['DT'].dt.date >= f_d[0]) & (df_m['DT'].dt.date <= f_d[1])]

            # AGRUPAMENTO VISUAL: Por Nota e Data
            agrupado = df_m.sort_values('DT', ascending=False).groupby(['Documento_Ref', 'Data_Hora', 'Tipo_Fluxo', 'Origem'])
            
            for (doc, data, tipo, ori), group in agrupado:
                with st.container(border=True):
                    st.markdown(f"**Nota:** `{doc}` | **Data:** `{data}`")
                    st.caption(f"Tipo: {tipo} | Origem: {ori}")
                    # Lista itens dentro da nota
                    for _, r in group.iterrows():
                        st.write(f"- {r['Nome_Produto']}: **{r['Quantidade']}**")
            
            st.download_button("📥 Baixar CSV", df_m.to_csv(index=False).encode('utf-8-sig'), "relatorio_escola.csv", use_container_width=True)
