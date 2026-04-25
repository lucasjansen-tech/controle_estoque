import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from modules.database import carregar_dados, salvar_dados
from modules.logic import calcular_estoque_atual
import io

# Tenta importar fpdf para o PDF. Caso não tenha no requirements, o app não trava.
try:
    from fpdf import FPDF
except ImportError:
    pass

def gerar_pdf_bytes(df, nome_escola):
    """Gera o conteúdo do PDF em formato de bytes para download."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, f"Relatorio de Movimentacao - {nome_escola}", ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(190, 10, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align='C')
    pdf.ln(10)

    # Cabeçalho da Tabela
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(25, 8, "Data", 1, 0, 'C', 1)
    pdf.cell(25, 8, "Doc/Nota", 1, 0, 'C', 1)
    pdf.cell(75, 8, "Produto", 1, 0, 'C', 1)
    pdf.cell(25, 8, "Qtd", 1, 0, 'C', 1)
    pdf.cell(40, 8, "Tipo", 1, 1, 'C', 1)

    # Dados
    pdf.set_font("Arial", '', 8)
    for _, row in df.iterrows():
        pdf.cell(25, 7, str(row['Data_Hora']), 1)
        pdf.cell(25, 7, str(row['Documento_Ref']), 1)
        pdf.cell(75, 7, str(row['Nome_Produto'])[:40], 1)
        pdf.cell(25, 7, str(row['Quantidade']), 1)
        pdf.cell(40, 7, str(row['Tipo_Fluxo']), 1, 1)

    return pdf.output(dest='S').encode('latin-1')

def renderizar_escola():
    user_data = st.session_state['usuario_dados']
    id_escola = user_data['id_escola']
    df_esc_ref = carregar_dados("db_escolas")
    df_cat = carregar_dados("db_catalogo")
    
    nome_escola = next((r['Nome_Escola'] for _, r in df_esc_ref.iterrows() if r['ID_Escola'] == id_escola), "Unidade Escolar")

    st.title(f"🏫 Portal da Escola: {nome_escola}")

    menu = st.sidebar.radio("Navegação Principal", [
        "🏠 Estoque e Gráficos", 
        "📦 Receber Materiais", 
        "✏️ Corrigir Lançamento",
        "🍳 Registrar Uso (Consumo)",
        "🍎 Cadastrar Novo Item",
        "📜 Relatórios e Documentos"
    ])

    st.sidebar.divider()
    if st.sidebar.button("🔄 Sincronizar Sistema", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # --- 1. ESTOQUE E GRÁFICOS ---
    if menu == "🏠 Estoque e Gráficos":
        st.subheader("📋 Situação do Almoxarifado")
        saldo = calcular_estoque_atual(id_escola)
        
        if not saldo.empty:
            df_f = pd.merge(saldo, df_cat, on='ID_Produto', how='left')
            st.markdown("**📊 Comparativo de Nível de Estoque**")
            st.bar_chart(df_f.set_index('Nome_Produto')['Saldo'])
            
            st.divider()
            cols = st.columns(3)
            for idx, row in df_f.iterrows():
                with cols[idx % 3].container(border=True):
                    st.markdown(f"## {row['Saldo']}")
                    st.caption(f"{row['Unidade_Medida']}")
                    st.markdown(f"**{row['Nome_Produto']}**")
        else:
            st.info("Nenhum item em estoque no momento.")

    # --- 2. RECEBER MATERIAIS ---
    elif menu == "📦 Receber Materiais":
        st.subheader("📦 Nova Entrada de Material")
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            origem = c1.selectbox("Origem", ["Agricultura Familiar", "SEMED", "Fornecedor"])
            doc_ref = c2.text_input("Nº Nota ou Documento")
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
                lista_salvar = []
                transacao_id = datetime.now().strftime('%y%m%d%H%M%S')
                for idx, it in enumerate(st.session_state.lista_itens):
                    if it['prod'] and it['qtd'] > 0:
                        id_p = df_cat[df_cat['Nome_Produto'] == it['prod']]['ID_Produto'].values[0]
                        lista_salvar.append([f"MOV-{transacao_id}-{idx}", data_r.strftime('%d/%m/%Y'), id_escola, "ENTRADA", origem, nome_escola, id_p, it['qtd'], user_data['email'], doc_ref])
                
                if lista_salvar:
                    df_novos = pd.DataFrame(lista_salvar, columns=['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','ID_Usuario','Documento_Ref'])
                    if salvar_dados(df_novos, "db_movimentacoes", modo='append'):
                        st.success("Recebimento registrado!")
                        st.session_state.lista_itens = [{'id': 0, 'prod': None, 'qtd': 0.0}]
                        st.rerun()
            else:
                st.error("O número da nota é obrigatório.")

    # --- 3. CORRIGIR LANÇAMENTO (SOLUÇÃO DE DUPLICIDADE DE CHAVES) ---
    elif menu == "✏️ Corrigir Lançamento":
        st.subheader("✏️ Ajustar ou Remover Itens")
        df_mov = carregar_dados("db_movimentacoes")
        minhas = df_mov[df_mov['ID_Escola'] == id_escola].copy()
        
        if not minhas.empty:
            minhas['Label'] = "Nota: " + minhas['Documento_Ref'] + " (" + minhas['Data_Hora'] + ")"
            opcoes = sorted(minhas['Label'].unique().tolist(), reverse=True)
            sel = st.selectbox("Buscar Nota/Documento:", [None] + opcoes)
            
            if sel:
                doc_o = sel.split("Nota: ")[1].split(" (")[0]
                data_o = sel.split("(")[1].replace(")", "")
                
                # Obtemos os itens da nota
                itens = minhas[(minhas['Documento_Ref'] == doc_o) & (minhas['Data_Hora'] == data_o)]
                itens = pd.merge(itens, df_cat[['ID_Produto', 'Nome_Produto']], on='ID_Produto', how='left')

                st.warning(f"Editando Nota: {doc_o} | Data: {data_o}")
                
                # Usamos enumerate para garantir chaves únicas em cada widget
                for idx, row in itens.reset_index().iterrows():
                    with st.container(border=True):
                        col1, col2, col3 = st.columns([3, 1, 1])
                        col1.markdown(f"**Item:** {row['Nome_Produto']}")
                        # Chave combinada com índice de loop para evitar DuplicateElementKey
                        nova_q = col2.number_input("Nova Qtd", value=float(row['Quantidade']), key=f"edit_q_{idx}_{row['ID_Movimentacao']}")
                        
                        if col3.button("🗑️ Excluir Item", key=f"edit_d_{idx}_{row['ID_Movimentacao']}"):
                            df_full = carregar_dados("db_movimentacoes")
                            # Remove exclusivamente o ID_Movimentacao selecionado
                            df_final = df_full[df_full['ID_Movimentacao'] != row['ID_Movimentacao']]
                            if salvar_dados(df_final, "db_movimentacoes", modo='overwrite'):
                                st.success("Item removido.")
                                st.rerun()

                if st.button("💾 Salvar Alterações de Quantidade", use_container_width=True, type="primary"):
                    df_full = carregar_dados("db_movimentacoes")
                    for idx, row in itens.reset_index().iterrows():
                        nova_v = st.session_state[f"edit_q_{idx}_{row['ID_Movimentacao']}"]
                        df_full.loc[df_full['ID_Movimentacao'] == row['ID_Movimentacao'], 'Quantidade'] = nova_v
                    
                    if salvar_dados(df_full, "db_movimentacoes", modo='overwrite'):
                        st.success("Dados atualizados!")
                        st.rerun()

    # --- 4. REGISTRAR USO (CONSUMO) ---
    elif menu == "🍳 Registrar Uso (Consumo)":
        st.subheader("🍳 Baixa de Material Diário")
        with st.form("f_consumo_unid", clear_on_submit=True):
            c1, c2 = st.columns(2)
            item_u = c1.selectbox("Produto", df_cat['Nome_Produto'].sort_values().tolist())
            qtd_u = c1.number_input("Quantidade Utilizada", min_value=0.01)
            obs_u = c2.text_input("Observação (Ex: Merenda Escolar)")
            data_u = c2.date_input("Data do Uso", datetime.now(), format="DD/MM/YYYY")
            
            if st.form_submit_button("Confirmar Saída", use_container_width=True):
                id_p = df_cat[df_cat['Nome_Produto'] == item_u]['ID_Produto'].values[0]
                df_saida = pd.DataFrame([[f"SAI-{datetime.now().strftime('%H%M%S')}", data_u.strftime('%d/%m/%Y'), id_escola, "SAÍDA", nome_escola, "CONSUMO INTERNO", id_p, qtd_u, user_data['email'], obs_u]], 
                                        columns=['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','ID_Usuario','Documento_Ref'])
                if salvar_dados(df_saida, "db_movimentacoes", modo='append'):
                    st.warning("Saída registrada.")
                    st.rerun()

    # --- 5. CADASTRAR NOVO ITEM ---
    elif menu == "🍎 Cadastrar Novo Item":
        st.subheader("🍎 Novo Item da Agricultura Familiar")
        with st.form("f_novo_cat"):
            c1, c2 = st.columns(2)
            id_p = c1.text_input("ID do Item (Ex: AF-PRODUTO)")
            nm_p = c1.text_input("Nome do Produto")
            un_p = c2.selectbox("Unidade", ["Kg", "Unid", "Maço", "Pct", "Cx"])
            if st.form_submit_button("Cadastrar no Catálogo"):
                novo_p = pd.DataFrame([[id_p, nm_p, "Agricultura Familiar", un_p]], columns=['ID_Produto', 'Nome_Produto', 'Categoria', 'Unidade_Medida'])
                if salvar_dados(novo_p, "db_catalogo"):
                    st.success("Item cadastrado!")
                    st.rerun()

    # --- 6. RELATÓRIOS E DOCUMENTOS (PDF E FILTROS DE PERÍODO) ---
    elif menu == "📜 Relatórios e Documentos":
        st.subheader("📜 Histórico e Documentos")
        df_mov = carregar_dados("db_movimentacoes")
        df_meu = df_mov[df_mov['ID_Escola'] == id_escola].copy()
        
        if not df_meu.empty:
            df_meu = pd.merge(df_meu, df_cat[['ID_Produto', 'Nome_Produto', 'Unidade_Medida']], on='ID_Produto', how='left')
            df_meu['DT'] = pd.to_datetime(df_meu['Data_Hora'], dayfirst=True, errors='coerce')
            
            with st.container(border=True):
                st.markdown("**🔍 Filtros de Relatório**")
                c1, c2 = st.columns(2)
                f_per = c1.selectbox("Período Rápido", ["Todo o Histórico", "Mês Atual", "Trimestral", "Semestral", "Anual"])
                f_tipo = c2.multiselect("Filtrar Tipo", ["ENTRADA", "SAÍDA", "TRANSFERÊNCIA"])

                hoje = datetime.now().date()
                if f_per == "Mês Atual":
                    df_meu = df_meu[df_meu['DT'].dt.month == hoje.month]
                elif f_per == "Trimestral":
                    df_meu = df_meu[df_meu['DT'].dt.date >= (hoje - timedelta(days=90))]
                elif f_per == "Semestral":
                    df_meu = df_meu[df_meu['DT'].dt.date >= (hoje - timedelta(days=180))]
                elif f_per == "Anual":
                    df_meu = df_meu[df_meu['DT'].dt.date >= (hoje - timedelta(days=365))]

                if f_tipo:
                    df_meu = df_meu[df_meu['Tipo_Fluxo'].isin(f_tipo)]

            # Exibição Agrupada
            for (doc, data), group in df_meu.sort_values('DT', ascending=False).groupby(['Documento_Ref', 'Data_Hora'], sort=False):
                with st.expander(f"📄 Nota: {doc} | Data: {data}"):
                    st.table(group[['Nome_Produto', 'Quantidade', 'Unidade_Medida', 'Tipo_Fluxo']])

            st.divider()
            col1, col2 = st.columns(2)
            
            # Excel
            csv = df_meu[['Data_Hora', 'Documento_Ref', 'Tipo_Fluxo', 'Nome_Produto', 'Quantidade', 'Unidade_Medida']].to_csv(index=False).encode('utf-8-sig')
            col1.download_button("📊 Baixar Excel Otimizado", csv, f"Relatorio_{id_escola}.csv", use_container_width=True)
            
            # PDF
            try:
                pdf_bytes = gerar_pdf_bytes(df_meu, nome_escola)
                col2.download_button("📄 Baixar PDF de Conferência", pdf_bytes, f"Conferencia_{id_escola}.pdf", "application/pdf", use_container_width=True)
            except Exception as e:
                col2.error("Erro ao gerar PDF. Verifique se a biblioteca 'fpdf' está instalada.")
        else:
            st.info("Nenhuma movimentação encontrada.")
