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
    """Registra movimentações críticas na aba db_logs"""
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

        st.info("Dica: Se o item chegou em Fardos ou Sacas, insira a Qtd convertida e anote a embalagem original na Observação.")

        if 'lista_itens' not in st.session_state:
            st.session_state.lista_itens = [{'id': 0, 'prod': None, 'qtd': 0.0, 'obs': ""}]

        for i, item in enumerate(st.session_state.lista_itens):
            with st.container(border=True):
                cp, cq, co, cd = st.columns([3, 1, 2, 0.5])
                st.session_state.lista_itens[i]['prod'] = cp.selectbox(f"Produto {i+1}", [None] + df_cat['Nome_Produto'].sort_values().tolist(), key=f"rec_p_{item['id']}")
                st.session_state.lista_itens[i]['qtd'] = cq.number_input("Qtd Final", min_value=0.0, key=f"rec_q_{item['id']}")
                st.session_state.lista_itens[i]['obs'] = co.text_input("Obs (Ex: 1 Saca 50kg)", key=f"rec_o_{item['id']}")
                
                if len(st.session_state.lista_itens) > 1:
                    if cd.button("❌", key=f"rec_del_{item['id']}"):
                        st.session_state.lista_itens.pop(i); st.rerun()

        if st.button("➕ Adicionar outro produto"):
            novo_id = st.session_state.lista_itens[-1]['id'] + 1
            st.session_state.lista_itens.append({'id': novo_id, 'prod': None, 'qtd': 0.0, 'obs': ""})
            st.rerun()

        if st.button("✅ SALVAR RECEBIMENTO", type="primary", use_container_width=True):
            if doc_ref:
                lista_s = []
                t_id = datetime.now().strftime('%y%m%d%H%M%S')
                for idx, it in enumerate(st.session_state.lista_itens):
                    if it['prod'] and it['qtd'] > 0:
                        cat_info = df_cat[df_cat['Nome_Produto'] == it['prod']].iloc[0]
                        lista_s.append([
                            f"MOV-{t_id}-{idx}", data_r.strftime('%d/%m/%Y'), id_escola, "ENTRADA", origem, nome_escola, 
                            cat_info['ID_Produto'], it['qtd'], cat_info['Unidade_Medida'], it['obs'], user_data['email'], doc_ref
                        ])
                if lista_s:
                    cols = ['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','Unidade_Medida','Observacao','ID_Usuario','Documento_Ref']
                    if salvar_dados(pd.DataFrame(lista_s, columns=cols), "db_movimentacoes", modo='append'):
                        st.success("Salvo!"); st.session_state.lista_itens = [{'id': 0, 'prod': None, 'qtd': 0.0, 'obs': ""}]; st.rerun()
            else:
                st.error("Número do documento é obrigatório.")

    # --- 3. CORRIGIR/ADICIONAR (CORREÇÃO DA COLUNA INDEX) ---
    elif menu == "✏️ Corrigir/Adicionar em Nota":
        st.subheader("✏️ Edição e Filtros de Documento")
        df_mov = carregar_dados("db_movimentacoes")
        if 'ids_para_excluir' not in st.session_state: st.session_state.ids_para_excluir = []

        if not df_mov.empty and 'ID_Escola' in df_mov.columns:
            minhas = df_mov[df_mov['ID_Escola'] == id_escola].copy()
            c_f1, c_f2 = st.columns(2)
            f_tipo_edit = c_f1.multiselect("Filtrar Tipo", ["ENTRADA", "TRANSFERÊNCIA", "SAÍDA"])
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
                # O drop=True garante que o Pandas não crie a coluna 'index' extra
                for idx, row in itens_nota.reset_index(drop=True).iterrows():
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
                            # Remoção de segurança de qualquer vestígio de index
                            l_up.pop('index', None) 
                            novos_v.append(l_up)

                with st.expander("➕ Inserir Novo Produto nesta Nota"):
                    n_p = st.selectbox("Produto", [None] + df_cat['Nome_Produto'].tolist())
                    n_q = st.number_input("Quantidade", min_value=0.0)
                    if st.button("Confirmar Inclusão"):
                        if n_p and n_q > 0:
                            cat_n = df_cat[df_cat['Nome_Produto'] == n_p].iloc[0]
                            nova_l = pd.DataFrame([[f"MOV-{datetime.now().strftime('%H%M%S')}-ADD", data_o, id_escola, "ENTRADA", itens_nota.iloc[0]['Origem'], nome_escola, cat_n['ID_Produto'], n_q, cat_n['Unidade_Medida'], "", user_data['email'], doc_o]], 
                                                 columns=['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','Unidade_Medida','Observacao','ID_Usuario','Documento_Ref'])
                            salvar_dados(pd.concat([df_mov, nova_l]), "db_movimentacoes", modo='overwrite')
                            registrar_log(user_data['email'], "ADIÇÃO", doc_o, n_p, n_q)
                            st.success("Adicionado!"); st.rerun()

                if st.button("💾 SALVAR ALTERAÇÕES", type="primary", use_container_width=True):
                    df_full = carregar_dados("db_movimentacoes")
                    ids_n = [str(x) for x in itens_nota['ID_Movimentacao'].tolist()]
                    
                    for mid in st.session_state.ids_para_excluir:
                        item_i = itens_nota[itens_nota['ID_Movimentacao'] == mid]
                        if not item_i.empty: registrar_log(user_data['email'], "EXCLUSÃO", doc_o, item_i.iloc[0]['Nome_Produto'], item_i.iloc[0]['Quantidade'])

                    df_r = df_full[~df_full['ID_Movimentacao'].astype(str).isin(ids_n)]
                    
                    # Garantia de que a coluna 'index' não passará daqui
                    df_n = pd.DataFrame(novos_v)
                    df_n = df_n.drop(columns=['Nome_Produto', 'Label', 'index', 'level_0'], errors='ignore')
                    
                    df_final = pd.concat([df_r, df_n]).fillna("")
                    if salvar_dados(df_final, "db_movimentacoes", modo='overwrite'):
                        st.session_state.ids_para_excluir = []; st.success("Nota Atualizada!"); st.rerun()

    # --- 4. REGISTRAR USO ---
    elif menu == "🍳 Registrar Uso (Consumo)":
        st.subheader("🍳 Registro de Baixa Diária")
        
        saldo_atual_df = calcular_estoque_atual(id_escola)
        c1, c2 = st.columns(2)
        p_u = c1.selectbox("O que foi utilizado?", df_cat['Nome_Produto'].sort_values().tolist())
        
        id_prod_u = df_cat[df_cat['Nome_Produto'] == p_u]['ID_Produto'].values[0]
        unid_medida_padrao = df_cat[df_cat['Nome_Produto'] == p_u]['Unidade_Medida'].values[0]
        saldo_item = 0.0
        if not saldo_atual_df.empty:
            match = saldo_atual_df[saldo_atual_df['ID_Produto'] == id_prod_u]
            if not match.empty: saldo_item = match.iloc[0]['Saldo']
        
        c1.info(f"💡 Saldo disponível: **{saldo_item} {unid_medida_padrao}**")
        
        q_u = c1.number_input("Quantidade para Saída", min_value=0.01, max_value=float(saldo_item) if saldo_item > 0 else 0.01)
        d_u = c2.date_input("Data do Uso", datetime.now(), format="DD/MM/YYYY")
        o_u = c2.text_input("Observação / Justificativa")
        
        if st.button("Confirmar Baixa de Estoque", type="primary", use_container_width=True):
            if saldo_item >= q_u:
                df_s = pd.DataFrame([[
                    f"SAI-{datetime.now().strftime('%H%M%S')}", d_u.strftime('%d/%m/%Y'), id_escola, "SAÍDA", 
                    nome_escola, "CONSUMO INTERNO", id_prod_u, q_u, unid_medida_padrao, o_u, user_data['email'], "USO DIÁRIO"
                ]], columns=['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','Unidade_Medida','Observacao','ID_Usuario','Documento_Ref'])
                
                if salvar_dados(df_s, "db_movimentacoes", modo='append'):
                    st.success("Saída registrada com sucesso!"); st.rerun()
            else:
                st.error("Quantidade informada é maior que o saldo em estoque.")

    # --- 5. CADASTRAR NOVO ITEM ---
    elif menu == "🍎 Cadastrar Novo Item":
        st.subheader("🍎 Novo Item Agricultura Familiar")
        with st.form("f_novo"):
            id_p = st.text_input("ID do Produto"); nm_p = st.text_input("Nome"); un_p = st.selectbox("Unidade Base", ["Kg", "Unid", "Maço", "Pct"])
            if st.form_submit_button("Cadastrar"):
                salvar_dados(pd.DataFrame([[id_p, nm_p, "Agricultura Familiar", un_p]], columns=['ID_Produto', 'Nome_Produto', 'Categoria', 'Unidade_Medida']), "db_catalogo"); st.rerun()

    # --- 6. RELATÓRIOS OFICIAIS ---
    elif menu == "📜 Relatórios Oficiais":
        st.subheader("📜 Histórico Consolidado")
        df_m = carregar_dados("db_movimentacoes")
        if not df_m.empty and 'ID_Escola' in df_m.columns:
            df_m = df_m[df_m['ID_Escola'] == id_escola].copy()
            df_m = pd.merge(df_m, df_cat[['ID_Produto', 'Nome_Produto']], on='ID_Produto', how='left')
            df_m['DT_OBJ'] = pd.to_datetime(df_m['Data_Hora'], dayfirst=True, errors='coerce')
            
            with st.container(border=True):
                st.markdown("**🔍 Filtros**")
                c1, c2 = st.columns(2)
                f_data = c1.date_input("Período", [datetime.now() - timedelta(days=30), datetime.now()], format="DD/MM/YYYY")
                f_tipo_rel = c2.multiselect("Tipo de Fluxo", ["ENTRADA", "SAÍDA", "TRANSFERÊNCIA"])
                
                if len(f_data) == 2: df_m = df_m[(df_m['DT_OBJ'].dt.date >= f_data[0]) & (df_m['DT_OBJ'].dt.date <= f_data[1])]
                if f_tipo_rel: df_m = df_m[df_m['Tipo_Fluxo'].isin(f_tipo_rel)]

            grupos = df_m.sort_values('DT_OBJ', ascending=False).groupby(['Documento_Ref', 'Data_Hora', 'ID_Usuario'], sort=False)
            for (doc, data, resp), group in grupos:
                with st.container(border=True):
                    st.markdown(f"📄 **Nota:** `{doc}` | 🗓️ **Data:** {data} | 👤 **Resp:** `{resp}`")
                    
                    cols_to_show = ['Nome_Produto', 'Quantidade']
                    if 'Unidade_Medida' in group.columns: cols_to_show.append('Unidade_Medida')
                    if 'Observacao' in group.columns: cols_to_show.append('Observacao')
                    cols_to_show.append('Tipo_Fluxo')
                    
                    st.dataframe(group[cols_to_show], use_container_width=True, hide_index=True)

            st.divider()
            col_d1, col_d2 = st.columns(2)
            
            csv_final = df_m.drop(columns=['DT_OBJ', 'Nome_Produto'], errors='ignore').to_csv(index=False).encode('utf-8-sig')
            col_d1.download_button("📊 Baixar Excel Detalhado", csv_final, f"Relatorio_{id_escola}.csv", use_container_width=True)
            
            if FPDF:
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", 'B', 14)
                pdf.cell(190, 10, "PREFEITURA MUNICIPAL DE RAPOSA", ln=True, align='C')
                pdf.set_font("Arial", '', 11)
                pdf.cell(190, 7, "Secretaria Municipal de Educacao - SEMED", ln=True, align='C')
                pdf.cell(190, 7, f"Controle da Unidade: {nome_escola}", ln=True, align='C')
                pdf.ln(8)
                
                for (doc, data, resp), group in grupos:
                    pdf.set_font("Arial", 'B', 10); pdf.set_fill_color(240, 240, 240)
                    pdf.cell(190, 8, f" NOTA: {doc} | DATA: {data} | RESPONSAVEL: {resp}", 1, 1, 'L', True)
                    pdf.set_font("Arial", 'B', 9)
                    pdf.cell(90, 7, " Produto", 1); pdf.cell(20, 7, " Qtd", 1); pdf.cell(20, 7, " Unid", 1); pdf.cell(60, 7, " Obs", 1); pdf.ln()
                    pdf.set_font("Arial", '', 8)
                    for _, r in group.iterrows():
                        pdf.cell(90, 6, f" {str(r['Nome_Produto'])[:40]}", 1)
                        pdf.cell(20, 6, f" {r['Quantidade']}", 1)
                        unid = r['Unidade_Medida'] if 'Unidade_Medida' in r else ""
                        obs = str(r['Observacao'])[:30] if 'Observacao' in r and pd.notna(r['Observacao']) else ""
                        pdf.cell(20, 6, f" {unid}", 1)
                        pdf.cell(60, 6, f" {obs}", 1); pdf.ln()
                    pdf.ln(4)
                
                pdf_bytes = pdf.output(dest='S').encode('latin-1')
                col_d2.download_button("📄 Baixar PDF Institucional", pdf_bytes, f"Relatorio_{id_escola}.pdf", "application/pdf", use_container_width=True)
            else:
                col_d2.warning("Instale 'fpdf' no requirements.txt")
