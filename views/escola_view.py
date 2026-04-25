import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from modules.database import carregar_dados, salvar_dados
from modules.logic import calcular_estoque_atual

def renderizar_escola():
    user_data = st.session_state['usuario_dados']
    id_escola = user_data['id_escola']
    
    # Bases de dados
    df_esc_ref = carregar_dados("db_escolas")
    df_cat = carregar_dados("db_catalogo")
    nome_escola = next((r['Nome_Escola'] for _, r in df_esc_ref.iterrows() if r['ID_Escola'] == id_escola), "Unidade Escolar")

    st.title(f"🏫 Portal da Escola: {nome_escola}")
    
    # Estados para Recebimento
    if 'lista_recebimento' not in st.session_state:
        st.session_state.lista_recebimento = [{'id': 0, 'produto': None, 'qtd': 0.0}]
    if 'contador_itens' not in st.session_state:
        st.session_state.contador_itens = 1

    menu = st.sidebar.radio("O que deseja fazer?", [
        "🏠 Meu Estoque Atual", 
        "📦 Receber Materiais", 
        "✏️ Corrigir Lançamento",
        "🍳 Registrar Uso (Consumo)",
        "📜 Relatórios Detalhados"
    ])

    st.sidebar.divider()
    if st.sidebar.button("🔄 Sincronizar Dados", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # --- 1. MEU ESTOQUE ATUAL (Cards) ---
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
            st.info("O estoque está vazio.")

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
                st.session_state.lista_recebimento[i]['produto'] = cp.selectbox(
                    f"Produto {i+1}", [None] + df_cat['Nome_Produto'].sort_values().tolist(), key=f"rec_p_{item['id']}"
                )
                st.session_state.lista_recebimento[i]['qtd'] = cq.number_input("Qtd", min_value=0.0, key=f"rec_q_{item['id']}")
                if len(st.session_state.lista_recebimento) > 1:
                    if cd.button("❌", key=f"rec_d_{item['id']}"):
                        st.session_state.lista_recebimento.pop(i)
                        st.rerun()

        if st.button("➕ Adicionar outro produto"):
            st.session_state.lista_recebimento.append({'id': st.session_state.contador_itens, 'produto': None, 'qtd': 0.0})
            st.session_state.contador_itens += 1
            st.rerun()

        if st.button("✅ SALVAR RECEBIMENTO", type="primary", use_container_width=True):
            if doc_ref:
                lista_s = []
                # Gerador de ID único por lote para evitar duplicatas de chave
                timestamp_lote = datetime.now().strftime('%y%m%d%H%M%S')
                for idx, it in enumerate(st.session_state.lista_recebimento):
                    if it['produto'] and it['qtd'] > 0:
                        id_p = df_cat[df_cat['Nome_Produto'] == it['produto']]['ID_Produto'].values[0]
                        lista_s.append([
                            f"MOV-{timestamp_lote}-{idx}", 
                            data_r.strftime('%d/%m/%Y'), id_escola, 
                            "ENTRADA" if origem != "SEMED" else "TRANSFERÊNCIA",
                            origem, nome_escola, id_p, it['qtd'], user_data['email'], doc_ref
                        ])
                if lista_s:
                    df_novo = pd.DataFrame(lista_s, columns=['ID_Movimentacao', 'Data_Hora', 'ID_Escola', 'Tipo_Fluxo', 'Origem', 'Destino', 'ID_Produto', 'Quantidade', 'ID_Usuario', 'Documento_Ref'])
                    if salvar_dados(df_novo, "db_movimentacoes", modo='append'):
                        st.success("Recebimento registrado!")
                        st.session_state.lista_recebimento = [{'id': 0, 'produto': None, 'qtd': 0.0}]
                        st.rerun()

    # --- 3. CORRIGIR LANÇAMENTO (SOLUÇÃO ERRO DUPLICATE KEY + EXCLUSÃO) ---
    elif menu == "✏️ Corrigir Lançamento":
        st.subheader("✏️ Ajustar ou Excluir Lançamentos")
        df_mov = carregar_dados("db_movimentacoes")
        minhas = df_mov[df_mov['ID_Escola'] == id_escola].copy()
        
        if not minhas.empty:
            minhas['Busca'] = "Nota: " + minhas['Documento_Ref'] + " (" + minhas['Data_Hora'] + ")"
            nota_sel = st.selectbox("Escolha a Nota/Data:", [None] + sorted(minhas['Busca'].unique().tolist(), reverse=True))
            
            if nota_sel:
                doc_o = nota_sel.split("Nota: ")[1].split(" (")[0]
                data_o = nota_sel.split("(")[1].replace(")", "")
                
                itens_nota = minhas[(minhas['Documento_Ref'] == doc_o) & (minhas['Data_Hora'] == data_o)]
                itens_nota = pd.merge(itens_nota, df_cat[['ID_Produto', 'Nome_Produto']], on='ID_Produto', how='left')
                
                st.info(f"Editando Nota: **{doc_o}** | Data: **{data_o}**")
                
                itens_editados = []
                if 'excluidos' not in st.session_state: st.session_state.excluidos = []

                for i, row in itens_nota.iterrows():
                    # Ignora visualmente se já foi marcado para exclusão nesta sessão
                    if row['ID_Movimentacao'] in st.session_state.excluidos:
                        continue

                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 1, 1])
                        c1.markdown(f"**Item:** {row['Nome_Produto']}")
                        # CHAVE ÚNICA CORRIGIDA: ed_q_{i}_{ID}
                        nova_q = c2.number_input("Qtd", value=float(row['Quantidade']), key=f"ed_q_{i}_{row['ID_Movimentacao']}")
                        
                        if c3.button("🗑️ Excluir", key=f"btn_del_{i}_{row['ID_Movimentacao']}", help="Remover este item"):
                            st.session_state.excluidos.append(row['ID_Movimentacao'])
                            st.rerun()
                        
                        item_up = row.to_dict()
                        item_up['Quantidade'] = nova_q
                        itens_editados.append(item_up)

                st.divider()
                if st.button("💾 SALVAR ALTERAÇÕES", type="primary", use_container_width=True):
                    df_full = carregar_dados("db_movimentacoes")
                    ids_originais = itens_nota['ID_Movimentacao'].tolist()
                    
                    # Remove originais e mantém o resto da rede
                    df_temp = df_full[~df_full['ID_Movimentacao'].isin(ids_originais)]
                    
                    # Processa os novos (filtrando os excluídos)
                    df_novos = pd.DataFrame(itens_editados)
                    if not df_novos.empty:
                        df_novos = df_novos[~df_novos['ID_Movimentacao'].isin(st.session_state.excluidos)]
                        df_novos = df_novos.drop(columns=['Nome_Produto', 'Busca', 'DT_OBJ'], errors='ignore')
                        df_final = pd.concat([df_temp, df_novos])
                    else:
                        df_final = df_temp

                    if salvar_dados(df_final, "db_movimentacoes", modo='overwrite'):
                        st.success("Alterações salvas!")
                        st.session_state.excluidos = []
                        st.rerun()
        else:
            st.info("Nada para corrigir.")

    # --- 4. REGISTRAR USO (CONSUMO) ---
    elif menu == "🍳 Registrar Uso (Consumo)":
        st.subheader("🍳 Registro de Uso Diário")
        with st.form("f_uso_escolar", clear_on_submit=True):
            c1, c2 = st.columns(2)
            p_uso = c1.selectbox("O que foi usado?", df_cat['Nome_Produto'].sort_values().tolist())
            q_uso = c1.number_input("Quantidade", min_value=0.01)
            d_uso = c2.date_input("Data", datetime.now(), format="DD/MM/YYYY")
            o_uso = c2.text_input("Observação", placeholder="Ex: Merenda Escolar")
            
            if st.form_submit_button("Confirmar Saída", use_container_width=True):
                id_p = df_cat[df_cat['Nome_Produto'] == p_uso]['ID_Produto'].values[0]
                df_s = pd.DataFrame([[f"SAI-{datetime.now().strftime('%y%m%d%H%M%S')}", d_uso.strftime('%d/%m/%Y'), id_escola, "SAÍDA", nome_escola, "CONSUMO INTERNO", id_p, q_uso, user_data['email'], o_uso]], 
                                    columns=['ID_Movimentacao', 'Data_Hora', 'ID_Escola', 'Tipo_Fluxo', 'Origem', 'Destino', 'ID_Produto', 'Quantidade', 'ID_Usuario', 'Documento_Ref'])
                if salvar_dados(df_s, "db_movimentacoes", modo='append'):
                    st.warning("Consumo registrado!")
                    st.rerun()

    # --- 5. RELATÓRIOS DETALHADOS (FILTROS DE PERÍODO RÁPIDO) ---
    elif menu == "📜 Relatórios Detalhados":
        st.subheader("📜 Histórico de Movimentação")
        df_m = carregar_dados("db_movimentacoes")
        df_m = df_m[df_m['ID_Escola'] == id_escola].copy()
        df_m['DT_OBJ'] = pd.to_datetime(df_m['Data_Hora'], dayfirst=True, errors='coerce')
        
        with st.container(border=True):
            st.markdown("**🔍 Filtros de Busca**")
            c1, c2 = st.columns(2)
            
            # Lógica de Período Rápido
            filtro_periodo = c1.selectbox("Período Pré-definido", ["Personalizado", "Mês Atual", "Trimestral (90 dias)", "Semestral (180 dias)", "Anual (365 dias)"])
            
            hoje = datetime.now().date()
            if filtro_periodo == "Mês Atual":
                data_padrao = [hoje.replace(day=1), hoje]
            elif filtro_periodo == "Trimestral (90 dias)":
                data_padrao = [hoje - timedelta(days=90), hoje]
            elif filtro_periodo == "Semestral (180 dias)":
                data_padrao = [hoje - timedelta(days=180), hoje]
            elif filtro_periodo == "Anual (365 dias)":
                data_padrao = [hoje - timedelta(days=365), hoje]
            else:
                data_padrao = [datetime(2026,1,1).date(), hoje]

            f_data = c2.date_input("Intervalo de Datas", data_padrao, format="DD/MM/YYYY")

        if not df_m.empty:
            df_m = pd.merge(df_m, df_cat[['ID_Produto', 'Nome_Produto']], on='ID_Produto', how='left')
            if len(f_data) == 2:
                df_m = df_m[(df_m['DT_OBJ'].dt.date >= f_data[0]) & (df_m['DT_OBJ'].dt.date <= f_data[1])]

            # Agrupamento Visual por Nota
            agrupado = df_m.sort_values('DT_OBJ', ascending=False).groupby(['Documento_Ref', 'Data_Hora', 'Tipo_Fluxo'])
            for (doc, data, tipo), group in agrupado:
                with st.container(border=True):
                    st.markdown(f"**Nota:** `{doc}` | **Data:** `{data}` | **Tipo:** `{tipo}`")
                    for _, r in group.iterrows():
                        st.write(f"• {r['Nome_Produto']}: **{r['Quantidade']}**")
            
            st.download_button("📥 Exportar Relatório", df_m.to_csv(index=False).encode('utf-8-sig'), f"Relatorio_{id_escola}.csv", use_container_width=True)
