import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from modules.database import carregar_dados, salvar_dados
from modules.logic import calcular_estoque_atual

# Tenta carregar fpdf para o PDF oficial
try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

def renderizar_escola():
    user_data = st.session_state['usuario_dados']
    id_escola = user_data['id_escola']
    df_esc_ref = carregar_dados("db_escolas")
    df_cat = carregar_dados("db_catalogo")
    
    nome_escola = next((r['Nome_Escola'] for _, r in df_esc_ref.iterrows() if r['ID_Escola'] == id_escola), "Unidade Escolar")

    # --- CABEÇALHO INSTITUCIONAL NO SISTEMA ---
    st.markdown(f"""
        <div style="background-color:#f0f2f6; padding:20px; border-radius:10px; border-left: 5px solid #007bff;">
            <h2 style="margin:0;">PREFEITURA MUNICIPAL DE RAPOSA</h2>
            <h4 style="margin:0; color:#555;">Secretaria Municipal de Educação - SEMED</h4>
            <hr>
            <p style="margin:0;"><b>Unidade:</b> {nome_escola} | <b>Operador:</b> {user_data['email']}</p>
        </div>
    """, unsafe_allow_html=True)
    st.write("")

    # --- MENU LATERAL (TODAS AS OPÇÕES RESTAURADAS E FIXAS) ---
    menu = st.sidebar.radio("Navegação do Sistema", [
        "🏠 Estoque Atual", 
        "📦 Receber Materiais", 
        "✏️ Corrigir/Adicionar em Nota",
        "🍳 Registrar Uso (Consumo)",
        "🍎 Cadastrar Novo Item",
        "📜 Relatórios Oficiais"
    ])

    st.sidebar.divider()
    if st.sidebar.button("🔄 Sincronizar Base de Dados", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # --- 1. ESTOQUE ATUAL ---
    if menu == "🏠 Estoque Atual":
        st.subheader("📋 Saldo em Prateleira")
        saldo = calcular_estoque_atual(id_escola)
        if not saldo.empty:
            df_f = pd.merge(saldo, df_cat, on='ID_Produto', how='left')
            st.bar_chart(df_f.set_index('Nome_Produto')['Saldo'])
            st.divider()
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
        st.subheader("📦 Registrar Entrada de Material")
        with st.container(border=True):
            st.markdown("**1. Dados da Entrega**")
            c1, c2, c3 = st.columns(3)
            origem = c1.selectbox("Origem", ["Agricultura Familiar", "SEMED", "Fornecedor"])
            doc_ref = c2.text_input("Nº da Nota / Documento")
            data_r = c3.date_input("Data da entrega", datetime.now(), format="DD/MM/YYYY")

        if 'lista_itens' not in st.session_state:
            st.session_state.lista_itens = [{'id': 0, 'prod': None, 'qtd': 0.0}]

        st.markdown("**2. Produtos Recebidos**")
        for i, item in enumerate(st.session_state.lista_itens):
            with st.container(border=True):
                col_p, col_q, col_d = st.columns([3, 1, 0.5])
                st.session_state.lista_itens[i]['prod'] = col_p.selectbox(f"Produto {i+1}", [None] + df_cat['Nome_Produto'].sort_values().tolist(), key=f"rec_p_{item['id']}")
                st.session_state.lista_itens[i]['qtd'] = col_q.number_input("Qtd", min_value=0.0, key=f"rec_q_{item['id']}")
                if len(st.session_state.lista_itens) > 1:
                    if col_d.button("❌", key=f"rec_del_{item['id']}"):
                        st.session_state.lista_itens.pop(i)
                        st.rerun()

        if st.button("➕ Adicionar outro produto"):
            novo_id = st.session_state.lista_itens[-1]['id'] + 1
            st.session_state.lista_itens.append({'id': novo_id, 'prod': None, 'qtd': 0.0})
            st.rerun()

        if st.button("✅ SALVAR RECEBIMENTO", type="primary", use_container_width=True):
            if doc_ref:
                lista_s = []
                t_id = datetime.now().strftime('%y%m%d%H%M%S')
                for idx, it in enumerate(st.session_state.lista_itens):
                    if it['prod'] and it['qtd'] > 0:
                        id_p = df_cat[df_cat['Nome_Produto'] == it['prod']]['ID_Produto'].values[0]
                        lista_s.append([f"MOV-{t_id}-{idx}", data_r.strftime('%d/%m/%Y'), id_escola, "ENTRADA", origem, nome_escola, id_p, it['qtd'], user_data['email'], doc_ref])
                if salvar_dados(pd.DataFrame(lista_s, columns=['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','ID_Usuario','Documento_Ref']), "db_movimentacoes", modo='append'):
                    st.success("Recebimento registrado com sucesso!")
                    st.session_state.lista_itens = [{'id': 0, 'prod': None, 'qtd': 0.0}]
                    st.rerun()
            else:
                st.error("O número do documento é obrigatório.")

    # --- 3. CORRIGIR/ADICIONAR EM NOTA (TRAVA DE SEGURANÇA) ---
    elif menu == "✏️ Corrigir/Adicionar em Nota":
        st.subheader("✏️ Edição e Adição em Documentos")
        df_mov = carregar_dados("db_movimentacoes")
        minhas = df_mov[df_mov['ID_Escola'] == id_escola].copy()
        
        if not minhas.empty:
            minhas['Label'] = "Nota: " + minhas['Documento_Ref'] + " (" + minhas['Data_Hora'] + ")"
            sel = st.selectbox("Selecione o Documento:", [None] + sorted(minhas['Label'].unique().tolist(), reverse=True))
            
            if sel:
                doc_o = sel.split("Nota: ")[1].split(" (")[0]
                data_o = sel.split("(")[1].replace(")", "")
                itens_edicao = minhas[(minhas['Documento_Ref'] == doc_o) & (minhas['Data_Hora'] == data_o)]
                itens_edicao = pd.merge(itens_edicao, df_cat[['ID_Produto', 'Nome_Produto']], on='ID_Produto', how='left')

                # Trava de segurança para exclusão
                trava_exclusao = st.sidebar.checkbox("🔓 Liberar Exclusão")

                # Listagem para Edição
                novos_valores = []
                excluidos_ids = []
                for idx, row in itens_edicao.reset_index().iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 1, 1])
                        c1.markdown(f"**Item:** {row['Nome_Produto']}")
                        val_q = c2.number_input("Qtd", value=float(row['Quantidade']), key=f"fix_q_{idx}_{row['ID_Movimentacao']}")
                        if trava_exclusao:
                            if c3.button("🗑️ Excluir", key=f"fix_d_{idx}_{row['ID_Movimentacao']}"):
                                excluidos_ids.append(row['ID_Movimentacao'])
                        else:
                            c3.write("🔒 Preservado")
                        
                        l_up = row.to_dict()
                        l_up['Quantidade'] = val_q
                        novos_valores.append(l_up)

                # Adicionar novo item na nota existente
                with st.expander("➕ Inserir novo produto nesta nota"):
                    new_p = st.selectbox("Produto", [None] + df_cat['Nome_Produto'].sort_values().tolist(), key="add_p_nota")
                    new_q = st.number_input("Quantidade", min_value=0.0, key="add_q_nota")
                    if st.button("Adicionar à Nota"):
                        if new_p and new_q > 0:
                            id_p_new = df_cat[df_cat['Nome_Produto'] == new_p]['ID_Produto'].values[0]
                            nova_linha = {
                                'ID_Movimentacao': f"MOV-{datetime.now().strftime('%H%M%S')}-ADD",
                                'Data_Hora': data_o, 'ID_Escola': id_escola, 'Tipo_Fluxo': "ENTRADA",
                                'Origem': itens_edicao.iloc[0]['Origem'], 'Destino': nome_escola,
                                'ID_Produto': id_p_new, 'Quantidade': new_q,
                                'ID_Usuario': user_data['email'], 'Documento_Ref': doc_o
                            }
                            df_full = carregar_dados("db_movimentacoes")
                            if salvar_dados(pd.concat([df_full, pd.DataFrame([nova_linha])]), "db_movimentacoes", modo='overwrite'):
                                st.success("Item adicionado!")
                                st.rerun()

                if st.button("💾 SALVAR ALTERAÇÕES", type="primary", use_container_width=True):
                    df_full = carregar_dados("db_movimentacoes")
                    ids_originais = itens_edicao['ID_Movimentacao'].tolist()
                    df_restante = df_full[~df_full['ID_Movimentacao'].isin(ids_originais)]
                    df_novos = pd.DataFrame(novos_valores)
                    df_novos = df_novos[~df_novos['ID_Movimentacao'].isin(excluidos_ids)]
                    df_novos = df_novos.drop(columns=['Nome_Produto', 'Label'], errors='ignore')
                    if salvar_dados(pd.concat([df_restante, df_novos]), "db_movimentacoes", modo='overwrite'):
                        st.success("Nota atualizada!")
                        st.rerun()

    # --- 4. REGISTRAR USO (CONSUMO) ---
    elif menu == "🍳 Registrar Uso (Consumo)":
        st.subheader("🍳 Registro de Baixa Diária")
        with st.form("f_uso", clear_on_submit=True):
            c1, c2 = st.columns(2)
            p_u = c1.selectbox("Produto Utilizado", df_cat['Nome_Produto'].sort_values().tolist())
            q_u = c1.number_input("Quantidade", min_value=0.01)
            d_u = c2.date_input("Data do Uso", datetime.now(), format="DD/MM/YYYY")
            o_u = c2.text_input("Finalidade (Ex: Merenda)")
            if st.form_submit_button("Confirmar Saída", use_container_width=True):
                id_p = df_cat[df_cat['Nome_Produto'] == p_u]['ID_Produto'].values[0]
                df_s = pd.DataFrame([[f"SAI-{datetime.now().strftime('%H%M%S')}", d_u.strftime('%d/%m/%Y'), id_escola, "SAÍDA", nome_escola, "CONSUMO INTERNO", id_p, q_u, user_data['email'], o_u]], 
                                    columns=['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','ID_Usuario','Documento_Ref'])
                if salvar_dados(df_s, "db_movimentacoes", modo='append'):
                    st.warning("Saída registrada!")
                    st.rerun()

    # --- 5. CADASTRAR NOVO ITEM ---
    elif menu == "🍎 Cadastrar Novo Item":
        st.subheader("🍎 Novo Item da Agricultura Familiar")
        with st.form("f_new_cat"):
            c1, c2 = st.columns(2)
            id_p = c1.text_input("Código (ID_Produto)")
            nm_p = c1.text_input("Nome do Produto")
            un_p = c2.selectbox("Unidade", ["Kg", "Unid", "Maço", "Pct", "Cx"])
            if st.form_submit_button("Cadastrar no Catálogo"):
                novo = pd.DataFrame([[id_p, nm_p, "Agricultura Familiar", un_p]], columns=['ID_Produto', 'Nome_Produto', 'Categoria', 'Unidade_Medida'])
                if salvar_dados(novo, "db_catalogo"):
                    st.success("Item cadastrado!")
                    st.rerun()

    # --- 6. RELATÓRIOS OFICIAIS (AGRUPAMENTO POR NOTA E IDENTIFICAÇÃO) ---
    elif menu == "📜 Relatórios Oficiais":
        st.subheader("📜 Histórico Consolidado de Movimentações")
        df_m = carregar_dados("db_movimentacoes")
        df_m = df_m[df_m['ID_Escola'] == id_escola].copy()
        
        if not df_m.empty:
            df_m = pd.merge(df_m, df_cat[['ID_Produto', 'Nome_Produto', 'Unidade_Medida']], on='ID_Produto', how='left')
            df_m['DT_OBJ'] = pd.to_datetime(df_m['Data_Hora'], dayfirst=True, errors='coerce')
            
            with st.container(border=True):
                st.markdown("**🔍 Filtros e Pesquisa**")
                c1, c2 = st.columns(2)
                f_prod = c1.multiselect("Filtrar por Produto", df_cat['Nome_Produto'].unique())
                f_tipo = c2.multiselect("Filtrar por Fluxo", ["ENTRADA", "SAÍDA", "TRANSFERÊNCIA"])
                
                if f_prod: df_m = df_m[df_m['Nome_Produto'].isin(f_prod)]
                if f_tipo: df_m = df_m[df_m['Tipo_Fluxo'].isin(f_tipo)]

            # AGRUPAMENTO POR NOTA E DATA
            grupos = df_m.sort_values('DT_OBJ', ascending=False).groupby(['Documento_Ref', 'Data_Hora', 'Origem', 'ID_Usuario'], sort=False)
            
            for (doc, data, ori, resp), group in grupos:
                with st.container(border=True):
                    # Cabeçalho da Nota
                    st.markdown(f"📄 **Nota/Documento:** `{doc}` | 🗓️ **Data:** {data}")
                    st.markdown(f"📍 **Origem:** {ori} | 👤 **Responsável pelo Lançamento:** `{resp}`")
                    # Tabela de Itens da Nota
                    st.table(group[['Nome_Produto', 'Quantidade', 'Unidade_Medida', 'Tipo_Fluxo']])

            st.divider()
            c1, c2 = st.columns(2)
            csv = df_m[['Data_Hora', 'Documento_Ref', 'Origem', 'ID_Usuario', 'Nome_Produto', 'Quantidade', 'Unidade_Medida']].to_csv(index=False).encode('utf-8-sig')
            c1.download_button("📊 Baixar Excel Detalhado", csv, f"Relatorio_{id_escola}.csv", use_container_width=True)
            
            if FPDF and c2.button("📄 Gerar PDF Oficial", use_container_width=True):
                st.info("Função PDF integrada: utilize a biblioteca fpdf no requirements.")
        else:
            st.info("Histórico vazio.")
