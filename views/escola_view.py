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

    # --- CABEÇALHO INSTITUCIONAL ---
    st.markdown(f"""
        <div style="background-color:#f8f9fa; padding:15px; border-radius:10px; border-left: 6px solid #004a99;">
            <h3 style="margin:0; color:#004a99;">PREFEITURA MUNICIPAL DE RAPOSA</h3>
            <p style="margin:0; color:#666;">Secretaria Municipal de Educação - SEMED</p>
            <p style="margin:0; font-size:14px;"><b>Unidade:</b> {nome_escola} | <b>Operador:</b> {user_data['email']}</p>
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
    if st.sidebar.button("🔄 Sincronizar Dados", use_container_width=True):
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
            origem = c1.selectbox("Origem", ["Agricultura Familiar", "SEMED", "Fornecedor"])
            doc_ref = c2.text_input("Nº da Nota / Documento")
            data_r = c3.date_input("Data da entrega", datetime.now(), format="DD/MM/YYYY")

        if 'lista_itens' not in st.session_state:
            st.session_state.lista_itens = [{'id': 0, 'prod': None, 'qtd': 0.0}]

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
                
                if lista_s:
                    df_final = pd.DataFrame(lista_s, columns=['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','ID_Usuario','Documento_Ref'])
                    if salvar_dados(df_final, "db_movimentacoes", modo='append'):
                        st.success("Recebimento registrado!")
                        st.session_state.lista_itens = [{'id': 0, 'prod': None, 'qtd': 0.0}]
                        st.rerun()
            else:
                st.error("O número do documento é obrigatório.")

    # --- 3. CORRIGIR/ADICIONAR EM NOTA (RESOLUÇÃO DO BUG 'NAN') ---
    elif menu == "✏️ Corrigir/Adicionar em Nota":
        st.subheader("✏️ Edição Avançada de Documentos")
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

                trava_exclusao = st.sidebar.checkbox("🔓 Liberar Exclusão de Itens")

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
                                st.toast(f"Item marcado para remoção.")
                        else:
                            c3.write("🔒 Bloqueado")

                        l_up = row.to_dict()
                        l_up['Quantidade'] = val_q
                        novos_valores.append(l_up)

                # --- Adicionar novo produto na mesma nota ---
                with st.expander("➕ Inserir outro produto nesta nota"):
                    n_p = st.selectbox("Produto", [None] + df_cat['Nome_Produto'].tolist(), key="add_p_ex")
                    n_q = st.number_input("Quantidade", min_value=0.0, key="add_q_ex")
                    if st.button("Adicionar"):
                        if n_p and n_q > 0:
                            id_p_n = df_cat[df_cat['Nome_Produto'] == n_p]['ID_Produto'].values[0]
                            nova_l = pd.DataFrame([[f"MOV-{datetime.now().strftime('%H%M%S')}-ADD", data_o, id_escola, "ENTRADA", itens_edicao.iloc[0]['Origem'], nome_escola, id_p_n, n_q, user_data['email'], doc_o]], 
                                                 columns=['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','ID_Usuario','Documento_Ref'])
                            if salvar_dados(pd.concat([df_mov, nova_l]), "db_movimentacoes", modo='overwrite'):
                                st.success("Item adicionado!")
                                st.rerun()

                if st.button("💾 SALVAR ALTERAÇÕES", type="primary", use_container_width=True):
                    # Lógica blindada contra NAN
                    df_full = carregar_dados("db_movimentacoes")
                    ids_nota = itens_edicao['ID_Movimentacao'].tolist()
                    df_restante = df_full[~df_full['ID_Movimentacao'].isin(ids_nota)]
                    
                    df_novos = pd.DataFrame(novos_valores)
                    df_novos = df_novos[~df_novos['ID_Movimentacao'].isin(excluidos_ids)]
                    
                    # Limpeza vital antes de salvar
                    df_novos = df_novos.drop(columns=['Nome_Produto', 'Label'], errors='ignore')
                    df_final = pd.concat([df_restante, df_novos]).reset_index(drop=True)
                    df_final = df_final.fillna("") # Substitui qualquer valor nulo por vazio
                    
                    if salvar_dados(df_final, "db_movimentacoes", modo='overwrite'):
                        st.success("Nota atualizada com sucesso!")
                        st.rerun()

    # --- 4. REGISTRAR USO ---
    elif menu == "🍳 Registrar Uso (Consumo)":
        st.subheader("🍳 Registro de Baixa Diária")
        with st.form("f_uso", clear_on_submit=True):
            c1, c2 = st.columns(2)
            p_u = c1.selectbox("Produto", df_cat['Nome_Produto'].sort_values().tolist())
            q_u = c1.number_input("Quantidade", min_value=0.01)
            d_u = c2.date_input("Data", datetime.now(), format="DD/MM/YYYY")
            o_u = c2.text_input("Observação (Ex: Merenda)")
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
        with st.form("f_novo"):
            id_p = st.text_input("ID do Item")
            nm_p = st.text_input("Nome")
            un_p = st.selectbox("Unidade", ["Kg", "Unid", "Maço", "Pct"])
            if st.form_submit_button("Cadastrar"):
                novo = pd.DataFrame([[id_p, nm_p, "Agricultura Familiar", un_p]], columns=['ID_Produto', 'Nome_Produto', 'Categoria', 'Unidade_Medida'])
                if salvar_dados(novo, "db_catalogo"):
                    st.success("Item cadastrado!")
                    st.rerun()

# --- 6. RELATÓRIOS OFICIAIS (AGRUPAMENTO POR NOTA E PDF) ---
    elif menu == "📜 Relatórios Oficiais":
        st.subheader("📜 Histórico Consolidado")
        df_m = carregar_dados("db_movimentacoes")
        df_m = df_m[df_m['ID_Escola'] == id_escola].copy()
        
        if not df_m.empty:
            df_m = pd.merge(df_m, df_cat[['ID_Produto', 'Nome_Produto', 'Unidade_Medida']], on='ID_Produto', how='left')
            df_m['DT_OBJ'] = pd.to_datetime(df_m['Data_Hora'], dayfirst=True, errors='coerce')
            df_m = df_m.sort_values('DT_OBJ', ascending=False)

            with st.container(border=True):
                st.markdown("**🔍 Filtros de Relatório**")
                c1, c2 = st.columns(2)
                f_per = c1.selectbox("Período Rápido", ["Todo o Histórico", "Mês Atual", "Últimos 90 dias"])
                f_tipo = c2.multiselect("Filtrar por Tipo", ["ENTRADA", "SAÍDA", "TRANSFERÊNCIA"])
                if f_tipo: df_m = df_m[df_m['Tipo_Fluxo'].isin(f_tipo)]

            # --- EXIBIÇÃO AGRUPADA POR BLOCOS DE NOTA (UX EXIGIDA) ---
            # Agrupamos por Nota, Data e Responsável para criar os blocos
            for (doc, data, resp), group in df_m.groupby(['Documento_Ref', 'Data_Hora', 'ID_Usuario'], sort=False):
                with st.container(border=True):
                    col_h1, col_h2 = st.columns([3, 1])
                    col_h1.markdown(f"📄 **Documento/Nota:** `{doc}`")
                    col_h1.markdown(f"🗓️ **Data do Recebimento:** {data}")
                    col_h2.markdown(f"👤 **Responsável:**")
                    col_h2.caption(resp)
                    
                    st.markdown("---")
                    # Tabela limpa de itens dentro daquela nota específica
                    st.dataframe(group[['Nome_Produto', 'Quantidade', 'Unidade_Medida', 'Tipo_Fluxo']], 
                                 use_container_width=True, hide_index=True)

            st.divider()
            col_d1, col_d2 = st.columns(2)
            
            # Exportação Excel (Cabeçalho Organizado)
            cols_ex = ['Data_Hora', 'Documento_Ref', 'Origem', 'ID_Usuario', 'Nome_Produto', 'Quantidade', 'Unidade_Medida']
            csv = df_m[cols_ex].to_csv(index=False).encode('utf-8-sig')
            col_d1.download_button("📊 Baixar Excel Otimizado", csv, f"Relatorio_{id_escola}.csv", use_container_width=True)
            
            # Geração de PDF Oficial Agrupado
            if FPDF:
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", 'B', 14)
                pdf.cell(190, 10, "PREFEITURA MUNICIPAL DE RAPOSA", ln=True, align='C')
                pdf.set_font("Arial", '', 11)
                pdf.cell(190, 7, "Secretaria Municipal de Educacao - SEMED", ln=True, align='C')
                pdf.cell(190, 7, "Controle de Recebimento de Materiais", ln=True, align='C')
                pdf.ln(5)
                pdf.set_font("Arial", 'B', 11)
                pdf.cell(190, 8, f"Unidade: {nome_escola}", ln=True, align='L')
                pdf.ln(5)

                # Conteúdo Agrupado no PDF
                for (doc, data, resp), group in df_m.groupby(['Documento_Ref', 'Data_Hora', 'ID_Usuario'], sort=False):
                    pdf.set_fill_color(230, 230, 230)
                    pdf.set_font("Arial", 'B', 10)
                    pdf.cell(190, 8, f" NOTA: {doc} | DATA: {data} | RESP: {resp}", 1, 1, 'L', True)
                    
                    pdf.set_font("Arial", 'B', 9)
                    pdf.cell(100, 7, " Item", 1); pdf.cell(30, 7, " Qtd", 1); pdf.cell(30, 7, " Unid", 1); pdf.cell(30, 7, " Tipo", 1); pdf.ln()
                    
                    pdf.set_font("Arial", '', 8)
                    for _, r in group.iterrows():
                        pdf.cell(100, 6, f" {str(r['Nome_Produto'])[:45]}", 1)
                        pdf.cell(30, 6, f" {r['Quantidade']}", 1)
                        pdf.cell(30, 6, f" {r['Unidade_Medida']}", 1)
                        pdf.cell(30, 6, f" {r['Tipo_Fluxo']}", 1); pdf.ln()
                    pdf.ln(3)

                pdf_out = pdf.output(dest='S').encode('latin-1')
                col_d2.download_button("📄 Baixar PDF Institucional", pdf_out, f"Relatorio_{id_escola}.pdf", "application/pdf", use_container_width=True)
        else:
            st.info("Histórico vazio.")
