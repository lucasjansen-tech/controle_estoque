import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from modules.database import carregar_dados, salvar_dados
from modules.logic import calcular_estoque_atual
import io

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
        <div style="background-color:#f8f9fa; padding:15px; border-radius:10px; border-left: 10px solid #004a99;">
            <h2 style="margin:0; color:#004a99; font-family: sans-serif;">Prefeitura Municipal de Raposa</h2>
            <h4 style="margin:0; color:#333; font-family: sans-serif;">Secretaria Municipal de Educação - SEMED</h4>
            <hr style="margin:8px 0;">
            <h5 style="margin:0; color:#555;"><b>Controle de Unidade:</b> {nome_escola}</h5>
        </div>
    """, unsafe_allow_html=True)
    st.write("")

    menu = st.sidebar.radio("Navegação Principal", [
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

    # --- 2. RECEBER MATERIAIS ---
    elif menu == "📦 Receber Materiais":
        st.subheader("📦 Registrar Entrada de Material")
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            origem = c1.selectbox("De onde veio?", ["Agricultura Familiar", "SEMED", "Fornecedor"])
            doc_ref = c2.text_input("Nº da Nota / Documento")
            data_r = c3.date_input("Data da entrega", datetime.now(), format="DD/MM/YYYY")

        if 'lista_itens' not in st.session_state:
            st.session_state.lista_itens = [{'id': 0, 'prod': None, 'qtd': 0.0}]

        for i, item in enumerate(st.session_state.lista_itens):
            with st.container(border=True):
                cp, cq, cd = st.columns([3, 1, 0.5])
                st.session_state.lista_itens[i]['prod'] = cp.selectbox(f"Produto {i+1}", [None] + df_cat['Nome_Produto'].sort_values().tolist(), key=f"rec_p_{item['id']}")
                st.session_state.lista_itens[i]['qtd'] = cq.number_input("Qtd", min_value=0.0, key=f"rec_q_{item['id']}")
                if len(st.session_state.lista_itens) > 1:
                    if cd.button("❌", key=f"rec_del_{item['id']}"):
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
                if lista_s:
                    if salvar_dados(pd.DataFrame(lista_s, columns=['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','ID_Usuario','Documento_Ref']), "db_movimentacoes", modo='append'):
                        st.success("Recebimento registrado!")
                        st.session_state.lista_itens = [{'id': 0, 'prod': None, 'qtd': 0.0}]
                        st.rerun()
            else:
                st.error("Documento obrigatório.")

    # --- 3. CORRIGIR/ADICIONAR EM NOTA (FIX BUG 'NAN' E PROTEÇÃO DA PRIMEIRA LINHA) ---
    elif menu == "✏️ Corrigir/Adicionar em Nota":
        st.subheader("✏️ Edição Avançada de Documentos")
        df_mov = carregar_dados("db_movimentacoes")
        
        # Garantir que a coluna de ID seja tratada como string para comparação
        if not df_mov.empty and 'ID_Movimentacao' in df_mov.columns:
            df_mov['ID_Movimentacao'] = df_mov['ID_Movimentacao'].astype(str)
            minhas = df_mov[df_mov['ID_Escola'] == id_escola].copy()
            
            if not minhas.empty:
                minhas['Label_Busca'] = "Nota: " + minhas['Documento_Ref'].astype(str) + " (" + minhas['Data_Hora'].astype(str) + ")"
                sel = st.selectbox("Selecione o Documento para editar:", [None] + sorted(minhas['Label_Busca'].unique().tolist(), reverse=True))
                
                if sel:
                    doc_o = sel.split("Nota: ")[1].split(" (")[0]
                    data_o = sel.split("(")[1].replace(")", "")
                    
                    itens_nota = minhas[(minhas['Documento_Ref'] == doc_o) & (minhas['Data_Hora'] == data_o)]
                    itens_nota = pd.merge(itens_nota, df_cat[['ID_Produto', 'Nome_Produto']], on='ID_Produto', how='left')

                    trava_excl = st.sidebar.checkbox("🔓 Liberar Exclusão de Itens")
                    
                    novos_dados_lista = []
                    excl_ids_lista = []

                    for idx, row in itens_nota.reset_index().iterrows():
                        with st.container(border=True):
                            c1, c2, c3 = st.columns([3, 1, 1])
                            c1.markdown(f"**Item:** {row['Nome_Produto']}")
                            val_q = c2.number_input("Qtd", value=float(row['Quantidade']), key=f"fix_q_{idx}_{row['ID_Movimentacao']}")
                            
                            if trava_excl:
                                if c3.button("🗑️ Excluir", key=f"fix_d_{idx}_{row['ID_Movimentacao']}"):
                                    excl_ids_lista.append(str(row['ID_Movimentacao']))
                                    st.toast("Item marcado para remoção.")
                            else: c3.write("🔒")

                            # Prepara linha para atualização
                            linha_dic = row.to_dict()
                            linha_dic['Quantidade'] = val_q
                            novos_dados_lista.append(linha_dic)

                    with st.expander("➕ Inserir outro produto nesta nota"):
                        n_p = st.selectbox("Produto", [None] + df_cat['Nome_Produto'].tolist(), key="add_p_ex")
                        n_q = st.number_input("Quantidade", min_value=0.0, key="add_q_ex")
                        if st.button("Adicionar"):
                            if n_p and n_q > 0:
                                id_p_n = df_cat[df_cat['Nome_Produto'] == n_p]['ID_Produto'].values[0]
                                nova_l = pd.DataFrame([[f"MOV-{datetime.now().strftime('%H%M%S')}-ADD", data_o, id_escola, "ENTRADA", itens_nota.iloc[0]['Origem'], nome_escola, id_p_n, n_q, user_data['email'], doc_o]], 
                                                     columns=['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','ID_Usuario','Documento_Ref'])
                                if salvar_dados(pd.concat([df_mov, nova_l]), "db_movimentacoes", modo='overwrite'):
                                    st.success("Item adicionado!"); st.rerun()

                    if st.button("💾 SALVAR ALTERAÇÕES", type="primary", use_container_width=True):
                        # Lógica Blindada: Reconstrói o DF sem perder a primeira linha ou cabeçalhos
                        df_full = carregar_dados("db_movimentacoes")
                        df_full['ID_Movimentacao'] = df_full['ID_Movimentacao'].astype(str)
                        
                        ids_da_nota = [str(x) for x in itens_nota['ID_Movimentacao'].tolist()]
                        
                        # Mantém o que NÃO é dessa nota (Preserva o restante do banco)
                        df_restante = df_full[~df_full['ID_Movimentacao'].isin(ids_da_nota)].copy()
                        
                        # Prepara os novos dados
                        df_editados = pd.DataFrame(novos_dados_lista)
                        df_editados['ID_Movimentacao'] = df_editados['ID_Movimentacao'].astype(str)
                        
                        # Remove os que o usuário marcou para excluir
                        df_editados = df_editados[~df_editados['ID_Movimentacao'].isin(excl_ids_lista)]
                        
                        # Limpa colunas auxiliares
                        cols_remover = ['Nome_Produto', 'Label_Busca']
                        df_editados = df_editados.drop(columns=[c for c in cols_remover if c in df_editados.columns], errors='ignore')
                        
                        # União final com preenchimento de vazios para evitar erro JSON/NAN
                        df_final_save = pd.concat([df_restante, df_editados], ignore_index=True).fillna("")
                        
                        # Garante a ordem das colunas originais do banco
                        colunas_originais = ['ID_Movimentacao', 'Data_Hora', 'ID_Escola', 'Tipo_Fluxo', 'Origem', 'Destino', 'ID_Produto', 'Quantidade', 'ID_Usuario', 'Documento_Ref']
                        df_final_save = df_final_save[colunas_originais]
                        
                        if salvar_dados(df_final_save, "db_movimentacoes", modo='overwrite'):
                            st.success("Dados atualizados!"); st.rerun()
            else: st.info("Selecione um documento.")
        else: st.warning("Planilha vazia ou erro de colunas.")

    # --- 4. REGISTRAR USO ---
    elif menu == "🍳 Registrar Uso (Consumo)":
        st.subheader("🍳 Registro de Baixa Diária")
        with st.form("f_uso", clear_on_submit=True):
            c1, c2 = st.columns(2)
            p_u = c1.selectbox("Produto", df_cat['Nome_Produto'].sort_values().tolist())
            q_u = c1.number_input("Quantidade", min_value=0.01)
            d_u = c2.date_input("Data", datetime.now(), format="DD/MM/YYYY")
            o_u = c2.text_input("Finalidade")
            if st.form_submit_button("Confirmar", use_container_width=True):
                id_p = df_cat[df_cat['Nome_Produto'] == p_u]['ID_Produto'].values[0]
                df_s = pd.DataFrame([[f"SAI-{datetime.now().strftime('%H%M%S')}", d_u.strftime('%d/%m/%Y'), id_escola, "SAÍDA", nome_escola, "CONSUMO INTERNO", id_p, q_u, user_data['email'], o_u]], 
                                    columns=['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','ID_Usuario','Documento_Ref'])
                salvar_dados(df_s, "db_movimentacoes", modo='append'); st.rerun()

    # --- 5. CADASTRAR NOVO ITEM ---
    elif menu == "🍎 Cadastrar Novo Item":
        st.subheader("🍎 Novo Item Agricultura Familiar")
        with st.form("f_novo"):
            id_p = st.text_input("ID"); nm_p = st.text_input("Nome"); un_p = st.selectbox("Unidade", ["Kg", "Unid", "Maço", "Pct"])
            if st.form_submit_button("Cadastrar"):
                salvar_dados(pd.DataFrame([[id_p, nm_p, "Agricultura Familiar", un_p]], columns=['ID_Produto', 'Nome_Produto', 'Categoria', 'Unidade_Medida']), "db_catalogo"); st.rerun()

    # --- 6. RELATÓRIOS OFICIAIS (AGRUPAMENTO INSTITUCIONAL) ---
    elif menu == "📜 Relatórios Oficiais":
        st.subheader("📜 Histórico Consolidado por Nota")
        df_m = carregar_dados("db_movimentacoes")
        
        if not df_m.empty and 'ID_Escola' in df_m.columns:
            df_m = df_m[df_m['ID_Escola'] == id_escola].copy()
            df_m = pd.merge(df_m, df_cat[['ID_Produto', 'Nome_Produto', 'Unidade_Medida']], on='ID_Produto', how='left')
            df_m['DT_OBJ'] = pd.to_datetime(df_m['Data_Hora'], dayfirst=True, errors='coerce')
            df_m = df_m.sort_values('DT_OBJ', ascending=False)

            # --- EXIBIÇÃO AGRUPADA EM BLOCOS (DOCUMENTO) ---
            # Agrupamos por Nota, Data e Responsável para criar blocos únicos
            grupos = df_m.groupby(['Documento_Ref', 'Data_Hora', 'ID_Usuario'], sort=False)
            
            for (doc, data, resp), group in grupos:
                with st.container(border=True):
                    c_h1, c_h2 = st.columns([3, 1])
                    c_h1.markdown(f"📄 **Documento/Nota:** `{doc}`")
                    c_h1.markdown(f"🗓️ **Data do Recebimento:** {data}")
                    c_h2.markdown(f"👤 **Responsável:**")
                    c_h2.caption(resp)
                    
                    st.write("**Produtos desta Nota:**")
                    # Tabela limpa e organizada
                    st.dataframe(group[['Nome_Produto', 'Quantidade', 'Unidade_Medida', 'Tipo_Fluxo']], 
                                 use_container_width=True, hide_index=True)

            st.divider()
            col_exp1, col_exp2 = st.columns(2)
            
            # Excel Organizado
            cols_ex = ['Data_Hora', 'Documento_Ref', 'Origem', 'ID_Usuario', 'Nome_Produto', 'Quantidade', 'Unidade_Medida']
            csv_final = df_m[cols_ex].to_csv(index=False).encode('utf-8-sig')
            col_exp1.download_button("📊 Baixar Excel (Organizado)", csv_final, f"Relatorio_{id_escola}.csv", use_container_width=True)
            
            # PDF Institucional
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
                    pdf.cell(100, 7, " Produto", 1); pdf.cell(30, 7, " Qtd", 1); pdf.cell(30, 7, " Unid", 1); pdf.cell(30, 7, " Fluxo", 1); pdf.ln()
                    pdf.set_font("Arial", '', 8)
                    for _, r in group.iterrows():
                        pdf.cell(100, 6, f" {str(r['Nome_Produto'])[:45]}", 1)
                        pdf.cell(30, 6, f" {r['Quantidade']}", 1)
                        pdf.cell(30, 6, f" {r['Unidade_Medida']}", 1)
                        pdf.cell(30, 6, f" {r['Tipo_Fluxo']}", 1); pdf.ln()
                    pdf.ln(4)
                
                pdf_bytes = pdf.output(dest='S').encode('latin-1')
                col_exp2.download_button("📄 Baixar PDF Institucional", pdf_bytes, f"Relatorio_{id_escola}.pdf", "application/pdf", use_container_width=True)
        else:
            st.info("Nenhuma movimentação para exibir.")
