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

def registrar_log(usuario, acao, doc, produto, qtd):
    """Garante que toda alteração crítica seja rastreada"""
    log_data = pd.DataFrame([[
        datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
        usuario, acao, doc, produto, qtd
    ]], columns=['Data_Hora', 'Usuario', 'Acao', 'Documento', 'Produto', 'Quantidade'])
    salvar_dados(log_data, "db_logs", modo='append')

def renderizar_escola():
    user_data = st.session_state['usuario_dados']
    id_escola = user_data['id_escola']
    df_esc_ref = carregar_dados("db_escolas")
    df_cat = carregar_dados("db_catalogo")
    
    nome_escola = next((r['Nome_Escola'] for _, r in df_esc_ref.iterrows() if r['ID_Escola'] == id_escola), "Unidade Escolar")

    # --- CABEÇALHO INSTITUCIONAL SIMÉTRICO ---
    st.markdown(f"""
        <div style="background-color:#f8f9fa; padding:20px; border-radius:10px; border-left: 10px solid #004a99; text-align: center;">
            <h2 style="margin:0; color:#004a99; font-size: 24px;">PREFEITURA MUNICIPAL DE RAPOSA</h2>
            <h2 style="margin:5px 0; color:#004a99; font-size: 24px;">SECRETARIA MUNICIPAL DE EDUCAÇÃO - SEMED</h2>
            <hr style="margin:10px 0;">
            <h5 style="margin:0; color:#555;"><b>Unidade de Ensino:</b> {nome_escola}</h5>
        </div>
    """, unsafe_allow_html=True)
    st.write("")

    menu = st.sidebar.radio("Navegação", [
        "🏠 Estoque Atual", 
        "📦 Receber Materiais", 
        "✏️ Corrigir/Adicionar em Nota",
        "🍳 Registrar Uso (Consumo)",
        "🍎 Cadastrar Novo Item",
        "📜 Relatórios Oficiais"
    ])

    st.sidebar.divider()
    if st.sidebar.button("🔄 Sincronizar Sistema", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # --- 1. ESTOQUE ATUAL ---
    if menu == "🏠 Estoque Atual":
        st.subheader("📋 Saldo em Prateleira")
        saldo_df = calcular_estoque_atual(id_escola)
        if not saldo_df.empty:
            df_f = pd.merge(saldo_df, df_cat, on='ID_Produto', how='left')
            st.markdown("**📊 Nível de Ocupação do Estoque**")
            st.bar_chart(df_f.set_index('Nome_Produto')['Saldo'])
            
            cols = st.columns(3)
            for idx, row in df_f.iterrows():
                with cols[idx % 3].container(border=True):
                    st.markdown(f"### {row['Saldo']}")
                    st.caption(f"{row['Unidade_Medida']}")
                    st.markdown(f"**{row['Nome_Produto']}**")
        else: st.info("Estoque vazio.")

    # --- 2. RECEBER MATERIAIS ---
    elif menu == "📦 Receber Materiais":
        st.subheader("📦 Nova Entrada de Material")
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            origem = c1.selectbox("Origem", ["Agricultura Familiar", "SEMED", "Fornecedor"])
            doc_ref = c2.text_input("Nº do Documento / Nota")
            data_r = c3.date_input("Data", datetime.now(), format="DD/MM/YYYY")

        if 'lista_itens' not in st.session_state:
            st.session_state.lista_itens = [{'id': 0, 'prod': None, 'qtd': 0.0}]

        for i, item in enumerate(st.session_state.lista_itens):
            with st.container(border=True):
                cp, cq, cd = st.columns([3, 1, 0.5])
                st.session_state.lista_itens[i]['prod'] = cp.selectbox(f"Produto {i+1}", [None] + df_cat['Nome_Produto'].sort_values().tolist(), key=f"rec_p_{item['id']}")
                st.session_state.lista_itens[i]['qtd'] = cq.number_input("Qtd", min_value=0.0, key=f"rec_q_{item['id']}")
                if len(st.session_state.lista_itens) > 1:
                    if cd.button("❌", key=f"rec_del_{item['id']}"):
                        st.session_state.lista_itens.pop(i); st.rerun()

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
                    st.success("Salvo!"); st.session_state.lista_itens = [{'id': 0, 'prod': None, 'qtd': 0.0}]; st.rerun()

    # --- 3. CORRIGIR/ADICIONAR (COM FILTRO DE TIPO E TRAVA DE EXCLUSÃO) ---
    elif menu == "✏️ Corrigir/Adicionar em Nota":
        st.subheader("✏️ Edição e Filtros de Documento")
        df_mov = carregar_dados("db_movimentacoes")
        minhas = df_mov[df_mov['ID_Escola'] == id_escola].copy()
        
        if 'ids_para_excluir' not in st.session_state: st.session_state.ids_para_excluir = []

        if not minhas.empty:
            c_f1, c_f2 = st.columns(2)
            f_tipo_edit = c_f1.multiselect("Filtrar Tipo de Nota", ["ENTRADA", "TRANSFERÊNCIA", "SAÍDA"])
            if f_tipo_edit: minhas = minhas[minhas['Tipo_Fluxo'].isin(f_tipo_edit)]
            
            minhas['Label'] = "Nota: " + minhas['Documento_Ref'].astype(str) + " (" + minhas['Data_Hora'].astype(str) + ")"
            sel = st.selectbox("Selecione o Documento para Alterar:", [None] + sorted(minhas['Label'].unique().tolist(), reverse=True))
            
            if sel:
                doc_o = sel.split("Nota: ")[1].split(" (")[0]
                data_o = sel.split("(")[1].replace(")", "")
                itens_nota = minhas[(minhas['Documento_Ref'] == doc_o) & (minhas['Data_Hora'] == data_o)]
                itens_nota = pd.merge(itens_nota, df_cat[['ID_Produto', 'Nome_Produto']], on='ID_Produto', how='left')

                trava_excl = st.sidebar.checkbox("🔓 Liberar Exclusão Permanente")
                
                novos_v = []
                for idx, row in itens_nota.reset_index().iterrows():
                    is_ex = str(row['ID_Movimentacao']) in st.session_state.ids_para_excluir
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 1, 1])
                        c1.markdown(f"{'<s>' if is_ex else ''}**Item:** {row['Nome_Produto']}{'</s>' if is_ex else ''}", unsafe_allow_html=True)
                        val_q = c2.number_input("Qtd", value=float(row['Quantidade']), key=f"ed_q_{idx}_{row['ID_Movimentacao']}", disabled=is_ex)
                        if trava_excl:
                            if not is_ex:
                                if c3.button("🗑️ Excluir", key=f"ex_{idx}"):
                                    st.session_state.ids_para_excluir.append(str(row['ID_Movimentacao'])); st.rerun()
                            else:
                                if c3.button("🔄 Desfazer", key=f"un_{idx}"):
                                    st.session_state.ids_para_excluir.remove(str(row['ID_Movimentacao'])); st.rerun()
                        else: c3.write("🔒")
                        if not is_ex:
                            l_up = row.to_dict()
                            l_up['Quantidade'] = val_q
                            novos_v.append(l_up)

                with st.expander("➕ Inserir Novo Produto nesta Nota"):
                    n_p = st.selectbox("Produto", [None] + df_cat['Nome_Produto'].tolist())
                    n_q = st.number_input("Quantidade", min_value=0.0)
                    if st.button("Confirmar Inclusão"):
                        if n_p and n_q > 0:
                            id_p_new = df_cat[df_cat['Nome_Produto'] == n_p]['ID_Produto'].values[0]
                            nova_l = pd.DataFrame([[f"MOV-{datetime.now().strftime('%H%M%S')}-ADD", data_o, id_escola, "ENTRADA", itens_nota.iloc[0]['Origem'], nome_escola, id_p_new, n_q, user_data['email'], doc_o]], 
                                                 columns=['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','ID_Usuario','Documento_Ref'])
                            salvar_dados(pd.concat([df_mov, nova_l]), "db_movimentacoes", modo='overwrite')
                            registrar_log(user_data['email'], "ADIÇÃO", doc_o, n_p, n_q)
                            st.success("Adicionado!"); st.rerun()

                if st.button("💾 SALVAR ALTERAÇÕES", type="primary", use_container_width=True):
                    df_full = carregar_dados("db_movimentacoes")
                    ids_n = [str(x) for x in itens_nota['ID_Movimentacao'].tolist()]
                    
                    for mid in st.session_state.ids_para_excluir:
                        item_i = itens_nota[itens_nota['ID_Movimentacao'] == mid]
                        if not item_i.empty: registrar_log(user_data['email'], "EXCLUSÃO", doc_o, item_i.iloc[0]['Nome_Produto'], item_i.iloc[0]['Quantidade'])

                    df_r = df_full[~df_full['ID_Movimentacao'].isin(ids_n)]
                    df_n = pd.DataFrame(novos_v).drop(columns=['Nome_Produto', 'Label'], errors='ignore')
                    df_final = pd.concat([df_r, df_n]).fillna("")
                    if salvar_dados(df_final, "db_movimentacoes", modo='overwrite'):
                        st.session_state.ids_para_excluir = []; st.success("Nota Atualizada!"); st.rerun()

    # --- 4. REGISTRAR USO (COM SALDO EM TEMPO REAL) ---
    elif menu == "🍳 Registrar Uso (Consumo)":
        st.subheader("🍳 Registro de Baixa Diária")
        st.markdown("Verifique o saldo disponível antes de confirmar a saída.")
        
        saldo_atual_df = calcular_estoque_atual(id_escola)
        
        with st.form("f_uso", clear_on_submit=True):
            col1, col2 = st.columns(2)
            p_u = col1.selectbox("O que foi utilizado?", df_cat['Nome_Produto'].sort_values().tolist())
            
            # --- UX: MOSTRAR SALDO DO ITEM SELECIONADO ---
            id_prod_u = df_cat[df_cat['Nome_Produto'] == p_u]['ID_Produto'].values[0]
            saldo_item = 0.0
            if not saldo_atual_df.empty:
                match = saldo_atual_df[saldo_atual_df['ID_Produto'] == id_prod_u]
                if not match.empty: saldo_item = match.iloc[0]['Saldo']
            
            col1.info(f"💡 Saldo disponível em estoque: **{saldo_item}**")
            
            q_u = col1.number_input("Quantidade para Saída", min_value=0.01, max_value=float(saldo_item) if saldo_item > 0 else 0.01)
            d_u = col2.date_input("Data do Uso", datetime.now(), format="DD/MM/YYYY")
            o_u = col2.text_input("Observação (Ex: Merenda Manhã)")
            
            if st.form_submit_button("Confirmar Baixa", use_container_width=True):
                df_s = pd.DataFrame([[f"SAI-{datetime.now().strftime('%H%M%S')}", d_u.strftime('%d/%m/%Y'), id_escola, "SAÍDA", nome_escola, "CONSUMO INTERNO", id_prod_u, q_u, user_data['email'], o_u]], 
                                    columns=['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','ID_Usuario','Documento_Ref'])
                if salvar_dados(df_s, "db_movimentacoes", modo='append'):
                    st.warning("Saída registrada!"); st.rerun()

    # --- 5. CADASTRAR NOVO ITEM ---
    elif menu == "🍎 Cadastrar Novo Item":
        st.subheader("🍎 Novo Item Agricultura Familiar")
        with st.form("f_novo"):
            id_p = st.text_input("ID do Produto (Ex: AF-FRUTA)"); nm_p = st.text_input("Nome"); un_p = st.selectbox("Unidade", ["Kg", "Unid", "Maço", "Pct"])
            if st.form_submit_button("Cadastrar"):
                salvar_dados(pd.DataFrame([[id_p, nm_p, "Agricultura Familiar", un_p]], columns=['ID_Produto', 'Nome_Produto', 'Categoria', 'Unidade_Medida']), "db_catalogo"); st.rerun()

    # --- 6. RELATÓRIOS OFICIAIS (AGRUPAMENTO E FILTROS DE PERÍODO/TIPO) ---
    elif menu == "📜 Relatórios Oficiais":
        st.subheader("📜 Histórico Consolidado")
        df_m = carregar_dados("db_movimentacoes")
        if not df_m.empty:
            df_m = df_m[df_m['ID_Escola'] == id_escola].copy()
            df_m = pd.merge(df_m, df_cat[['ID_Produto', 'Nome_Produto', 'Unidade_Medida']], on='ID_Produto', how='left')
            df_m['DT_OBJ'] = pd.to_datetime(df_m['Data_Hora'], dayfirst=True, errors='coerce')
            
            with st.container(border=True):
                st.markdown("**🔍 Filtros de Pesquisa Avançada**")
                c1, c2 = st.columns(2)
                f_data = c1.date_input("Filtrar por Período", [datetime.now() - timedelta(days=30), datetime.now()], format="DD/MM/YYYY")
                f_tipo_rel = c2.multiselect("Filtrar por Tipo de Fluxo", ["ENTRADA", "SAÍDA", "TRANSFERÊNCIA"])
                
                # Aplicar Filtros
                if len(f_data) == 2: df_m = df_m[(df_m['DT_OBJ'].dt.date >= f_data[0]) & (df_m['DT_OBJ'].dt.date <= f_data[1])]
                if f_tipo_rel: df_m = df_m[df_m['Tipo_Fluxo'].isin(f_tipo_rel)]

            # AGRUPAMENTO POR NOTA
            grupos = df_m.sort_values('DT_OBJ', ascending=False).groupby(['Documento_Ref', 'Data_Hora', 'ID_Usuario'], sort=False)
            for (doc, data, resp), group in grupos:
                with st.container(border=True):
                    st.markdown(f"📄 **Nota/Documento:** `{doc}` | 🗓️ **Data:** {data} | 👤 **Resp:** `{resp}`")
                    st.table(group[['Nome_Produto', 'Quantidade', 'Unidade_Medida', 'Tipo_Fluxo']])
