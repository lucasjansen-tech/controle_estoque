import streamlit as st
import pandas as pd
from datetime import datetime
from modules.database import carregar_dados, salvar_dados
from modules.logic import calcular_estoque_atual

def renderizar_escola():
    user_data = st.session_state['usuario_dados']
    id_escola = user_data['id_escola']
    
    # Busca dados bases
    df_esc_ref = carregar_dados("db_escolas")
    df_cat = carregar_dados("db_catalogo")
    nome_escola = next((r['Nome_Escola'] for _, r in df_esc_ref.iterrows() if r['ID_Escola'] == id_escola), "Unidade Escolar")

    st.title(f"🏫 Portal da Escola: {nome_escola}")
    
    # Estado para recebimento dinâmico de múltiplos itens
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

    # --- 1. MEU ESTOQUE ATUAL ---
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
            st.info("O estoque desta unidade está vazio.")

    # --- 2. RECEBER MATERIAIS ---
    elif menu == "📦 Receber Materiais":
        st.subheader("📦 Registrar Chegada de Carga")
        
        with st.container(border=True):
            st.markdown("**1. Dados da Entrega**")
            c1, c2, c3 = st.columns(3)
            origem = c1.selectbox("Origem", ["Agricultura Familiar", "SEMED", "Fornecedor"])
            doc_ref = c2.text_input("Nº Nota/Documento")
            data_r = c3.date_input("Data da entrega", datetime.now(), format="DD/MM/YYYY")

        st.markdown("**2. Itens da Carga**")
        for i, item in enumerate(st.session_state.lista_recebimento):
            with st.container(border=True):
                cp, cq, cd = st.columns([3, 1, 0.5])
                st.session_state.lista_recebimento[i]['produto'] = cp.selectbox(
                    f"Produto {i+1}", [None] + df_cat['Nome_Produto'].sort_values().tolist(), key=f"rec_p_{item['id']}"
                )
                st.session_state.lista_recebimento[i]['qtd'] = cq.number_input("Qtd", min_value=0.0, key=f"rec_q_{item['id']}")
                if len(st.session_state.lista_recebimento) > 1:
                    if cd.button("❌", key=f"rec_d_{item['id']}", help="Remover item da lista"):
                        st.session_state.lista_recebimento.pop(i)
                        st.rerun()

        if st.button("➕ Adicionar outro produto ao recebimento"):
            st.session_state.lista_recebimento.append({'id': st.session_state.contador_itens, 'produto': None, 'qtd': 0.0})
            st.session_state.contador_itens += 1
            st.rerun()

        st.divider()
        if st.button("✅ SALVAR RECEBIMENTO COMPLETO", type="primary", use_container_width=True):
            if doc_ref:
                lista_s = []
                for it in st.session_state.lista_recebimento:
                    if it['produto'] and it['qtd'] > 0:
                        id_p = df_cat[df_cat['Nome_Produto'] == it['produto']]['ID_Produto'].values[0]
                        lista_s.append([
                            f"MOV-{datetime.now().strftime('%y%m%d%H%M%S')}-{it['id']}",
                            data_r.strftime('%d/%m/%Y'), id_escola, 
                            "ENTRADA" if origem != "SEMED" else "TRANSFERÊNCIA",
                            origem, nome_escola, id_p, it['qtd'], user_data['email'], doc_ref
                        ])
                if lista_s:
                    df_novo = pd.DataFrame(lista_s, columns=['ID_Movimentacao', 'Data_Hora', 'ID_Escola', 'Tipo_Fluxo', 'Origem', 'Destino', 'ID_Produto', 'Quantidade', 'ID_Usuario', 'Documento_Ref'])
                    if salvar_dados(df_novo, "db_movimentacoes", modo='append'):
                        st.success("Recebimento registrado com sucesso!")
                        st.session_state.lista_recebimento = [{'id': 0, 'produto': None, 'qtd': 0.0}]
                        st.rerun()
                else:
                    st.warning("Adicione produtos e quantidades válidas.")
            else:
                st.error("O número do documento é obrigatório.")

    # --- 3. CORRIGIR LANÇAMENTO (COM EXCLUSÃO INDIVIDUAL) ---
    elif menu == "✏️ Corrigir Lançamento":
        st.subheader("✏️ Ajustar ou Excluir Itens de uma Nota")
        df_mov = carregar_dados("db_movimentacoes")
        minhas = df_mov[df_mov['ID_Escola'] == id_escola].copy()
        
        if not minhas.empty:
            # Identificador amigável: Nota + Data
            minhas['Busca'] = "Nota: " + minhas['Documento_Ref'] + " (" + minhas['Data_Hora'] + ")"
            opcoes = sorted(minhas['Busca'].unique().tolist(), reverse=True)
            nota_sel = st.selectbox("Escolha o Recebimento para editar:", [None] + opcoes)
            
            if nota_sel:
                doc_o = nota_sel.split("Nota: ")[1].split(" (")[0]
                data_o = nota_sel.split("(")[1].replace(")", "")
                
                # Filtra os itens daquela nota específica
                itens_nota = minhas[(minhas['Documento_Ref'] == doc_o) & (minhas['Data_Hora'] == data_o)]
                itens_nota = pd.merge(itens_nota, df_cat[['ID_Produto', 'Nome_Produto']], on='ID_Produto', how='left')
                
                st.info(f"Editando Nota: **{doc_o}** | Data: **{data_o}**")
                
                # Lista para rastrear o que será salvo ou removido
                editados = []
                removidos = []

                for i, row in itens_nota.iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 1, 1])
                        c1.markdown(f"**Item:** {row['Nome_Produto']}")
                        nova_q = c2.number_input("Nova Qtd", value=float(row['Quantidade']), key=f"ed_q_{row['ID_Movimentacao']}")
                        
                        # BOTÃO DE EXCLUSÃO INDIVIDUAL
                        if c3.button("🗑️ Excluir Item", key=f"ed_d_{row['ID_Movimentacao']}", help="Remove apenas este produto desta nota"):
                            removidos.append(row['ID_Movimentacao'])
                            st.toast(f"Item '{row['Nome_Produto']}' será removido ao salvar.")
                        
                        # Prepara dados atualizados
                        item_up = row.to_dict()
                        item_up['Quantidade'] = nova_q
                        editados.append(item_up)

                st.divider()
                if st.button("💾 SALVAR ALTERAÇÕES NA NOTA", type="primary", use_container_width=True):
                    df_full = carregar_dados("db_movimentacoes")
                    
                    # 1. Remove os registros originais desta nota
                    ids_originais = itens_nota['ID_Movimentacao'].tolist()
                    df_temp = df_full[~df_full['ID_Movimentacao'].isin(ids_originais)]
                    
                    # 2. Prepara os novos dados (removendo os marcados para exclusão)
                    df_novos_dados = pd.DataFrame(editados)
                    df_novos_dados = df_novos_dados[~df_novos_dados['ID_Movimentacao'].isin(removidos)]
                    
                    # Limpa colunas auxiliares antes de salvar
                    df_novos_dados = df_novos_dados.drop(columns=['Nome_Produto', 'Busca'], errors='ignore')
                    
                    # 3. Une tudo e salva
                    df_final = pd.concat([df_temp, df_novos_dados])
                    if salvar_dados(df_final, "db_movimentacoes", modo='overwrite'):
                        st.success("Nota atualizada com sucesso!")
                        st.rerun()
        else:
            st.info("Nenhum lançamento encontrado para correção.")

    # --- 4. REGISTRAR USO (CONSUMO) ---
    elif menu == "🍳 Registrar Uso (Consumo)":
        st.subheader("🍳 Registro de Uso Diário (Saída)")
        st.markdown("Informe o que foi utilizado na cozinha ou para limpeza hoje.")
        
        with st.form("f_consumo_unidade", clear_on_submit=True):
            c1, c2 = st.columns(2)
            prod_c = c1.selectbox("Produto Utilizado", df_cat['Nome_Produto'].sort_values().tolist())
            qtd_c = c1.number_input("Quantidade", min_value=0.01, help="Ex: 5.00")
            
            data_c = c2.date_input("Data do Uso", datetime.now(), format="DD/MM/YYYY")
            obs_c = c2.text_input("Finalidade / Observação", placeholder="Ex: Merenda Escolar - Arroz")
            
            if st.form_submit_button("Confirmar Saída do Estoque", use_container_width=True):
                id_p = df_cat[df_cat['Nome_Produto'] == prod_c]['ID_Produto'].values[0]
                
                df_baixa = pd.DataFrame([[
                    f"SAI-{datetime.now().strftime('%y%m%d%H%M%S')}", 
                    data_c.strftime('%d/%m/%Y'), id_escola, "SAÍDA", 
                    nome_escola, "CONSUMO INTERNO", id_p, qtd_c, 
                    user_data['email'], obs_c
                ]], columns=['ID_Movimentacao', 'Data_Hora', 'ID_Escola', 'Tipo_Fluxo', 'Origem', 'Destino', 'ID_Produto', 'Quantidade', 'ID_Usuario', 'Documento_Ref'])
                
                if salvar_dados(df_baixa, "db_movimentacoes", modo='append'):
                    st.warning(f"Baixa registrada: {qtd_c} de {prod_c} saiu do estoque.")
                    st.rerun()

    # --- 5. RELATÓRIOS AGRUPADOS POR NOTA ---
    elif menu == "📜 Relatórios da Unidade":
        st.subheader("📜 Histórico de Movimentação Agrupado")
        df_m = carregar_dados("db_movimentacoes")
        df_m = df_m[df_m['ID_Escola'] == id_escola].copy()
        
        if not df_m.empty:
            df_m = pd.merge(df_m, df_cat[['ID_Produto', 'Nome_Produto']], on='ID_Produto', how='left')
            
            with st.expander("🔍 Filtros de Pesquisa"):
                f_tipo = st.multiselect("Tipo de Movimento", ["ENTRADA", "SAÍDA", "TRANSFERÊNCIA"])
                f_data = st.date_input("Filtrar Período", [datetime(2024,1,1), datetime.now()], format="DD/MM/YYYY")
            
            # Aplicação de filtros
            df_m['DT_OBJ'] = pd.to_datetime(df_m['Data_Hora'], dayfirst=True, errors='coerce')
            if f_tipo: df_m = df_m[df_m['Tipo_Fluxo'].isin(f_tipo)]
            if len(f_data) == 2:
                df_m = df_m[(df_m['DT_OBJ'].dt.date >= f_data[0]) & (df_m['DT_OBJ'].dt.date <= f_data[1])]

            st.write(f"Mostrando histórico de **{nome_escola}**:")

            # Lógica de Agrupamento Visual por Nota e Data
            movimentacoes_agrupadas = df_m.sort_values('DT_OBJ', ascending=False).groupby(['Documento_Ref', 'Data_Hora', 'Tipo_Fluxo', 'Origem'])
            
            for (doc, data, tipo, ori), group in movimentacoes_agrupadas:
                with st.container(border=True):
                    col_header1, col_header2 = st.columns([3, 1])
                    # Título do bloco por Nota
                    col_header1.markdown(f"📄 **Nota/Documento:** `{doc}`")
                    col_header1.caption(f"🗓️ Data: {data} | 🔄 Fluxo: {tipo} | 📍 Origem: {ori}")
                    
                    # Lista os itens dentro desta nota específica
                    st.markdown("**Produtos deste lançamento:**")
                    for _, item in group.iterrows():
                        st.write(f"• {item['Nome_Produto']}: **{item['Quantidade']}**")

            st.divider()
            csv_data = df_m.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 Baixar Relatório Completo (CSV)", csv_data, f"Relatorio_{id_escola}.csv", use_container_width=True)
        else:
            st.info("Nenhuma movimentação registrada para esta unidade.")
