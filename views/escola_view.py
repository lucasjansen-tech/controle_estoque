import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from modules.database import carregar_dados, salvar_dados
from modules.logic import calcular_estoque_atual
import io

# Importação segura do FPDF para o PDF
try:
    from fpdf import FPDF
except ImportError:
    pass

def gerar_pdf_conferencia(df, nome_unidade):
    """Gera o PDF formatado para download imediato"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, f"Relatório de Movimentação - {nome_unidade}", ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(190, 10, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align='C')
    pdf.ln(10)

    # Cabeçalho
    pdf.set_fill_color(200, 220, 255)
    pdf.set_font("Arial", 'B', 10)
    cols = [("Data", 25), ("Doc/Nota", 25), ("Produto", 80), ("Qtd", 20), ("Tipo", 40)]
    for col_name, width in cols:
        pdf.cell(width, 8, col_name, 1, 0, 'C', 1)
    pdf.ln()

    # Linhas
    pdf.set_font("Arial", '', 9)
    for _, row in df.iterrows():
        pdf.cell(25, 7, str(row['Data_Hora']), 1)
        pdf.cell(25, 7, str(row['Documento_Ref']), 1)
        pdf.cell(80, 7, str(row['Nome_Produto'])[:45], 1)
        pdf.cell(20, 7, str(row['Quantidade']), 1)
        pdf.cell(40, 7, str(row['Tipo_Fluxo']), 1, 1)

    return pdf.output(dest='S').encode('latin-1')

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
        "🍎 Cadastrar Novo Item",
        "📜 Relatórios e Documentos"
    ])

    st.sidebar.divider()
    if st.sidebar.button("🔄 Sincronizar Sistema", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # --- 1. ESTOQUE E GRÁFICOS ---
    if menu == "🏠 Estoque e Gráficos":
        st.subheader("📋 Saldo Atual")
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
            st.info("Nenhum item em estoque.")

    # --- 2. RECEBER MATERIAIS ---
    elif menu == "📦 Receber Materiais":
        st.subheader("📦 Nova Entrada")
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            origem = c1.selectbox("Origem", ["Agricultura Familiar", "SEMED", "Fornecedor"])
            doc_ref = c2.text_input("Nº Nota ou Documento")
            data_r = c3.date_input("Data", datetime.now(), format="DD/MM/YYYY")

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
                timestamp = datetime.now().strftime('%y%m%d%H%M%S')
                for idx, it in enumerate(st.session_state.lista_itens):
                    if it['prod'] and it['qtd'] > 0:
                        id_p = df_cat[df_cat['Nome_Produto'] == it['prod']]['ID_Produto'].values[0]
                        lista_s.append([f"MOV-{timestamp}-{idx}", data_r.strftime('%d/%m/%Y'), id_escola, "ENTRADA", origem, nome_escola, id_p, it['qtd'], user_data['email'], doc_ref])
                if lista_s:
                    if salvar_dados(pd.DataFrame(lista_s, columns=['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','ID_Usuario','Documento_Ref']), "db_movimentacoes", modo='append'):
                        st.success("Salvo!")
                        st.session_state.lista_itens = [{'id': 0, 'prod': None, 'qtd': 0.0}]
                        st.rerun()
            else:
                st.error("Número da nota obrigatório.")

    # --- 3. CORRIGIR LANÇAMENTO (SOLUÇÃO DEFINITIVA PARA BUG DE EXCLUSÃO E CHAVES) ---
    elif menu == "✏️ Corrigir Lançamento":
        st.subheader("✏️ Ajustar ou Remover Itens")
        df_mov = carregar_dados("db_movimentacoes")
        minhas = df_mov[df_mov['ID_Escola'] == id_escola].copy()
        
        if not minhas.empty:
            minhas['Label'] = "Nota: " + minhas['Documento_Ref'] + " (" + minhas['Data_Hora'] + ")"
            opcoes = sorted(minhas['Label'].unique().tolist(), reverse=True)
            sel = st.selectbox("Buscar Nota:", [None] + opcoes)
            
            if sel:
                doc_o = sel.split("Nota: ")[1].split(" (")[0]
                data_o = sel.split("(")[1].replace(")", "")
                
                # Filtro cirúrgico dos itens da nota
                itens = minhas[(minhas['Documento_Ref'] == doc_o) & (minhas['Data_Hora'] == data_o)]
                itens = pd.merge(itens, df_cat[['ID_Produto', 'Nome_Produto']], on='ID_Produto', how='left')

                st.info(f"Editando Nota: {doc_o} | Data: {data_o}")
                
                for idx, row in itens.reset_index().iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 1, 1])
                        c1.markdown(f"**Item:** {row['Nome_Produto']}")
                        # CHAVE ÚNICA PARA EVITAR StreamlitDuplicateElementKey
                        nova_q = c2.number_input("Qtd", value=float(row['Quantidade']), key=f"fix_q_{idx}_{row['ID_Movimentacao']}")
                        
                        # EXCLUSÃO UNITÁRIA (Focada apenas no ID da linha)
                        if c3.button("🗑️ Excluir", key=f"fix_d_{idx}_{row['ID_Movimentacao']}"):
                            df_completo = carregar_dados("db_movimentacoes")
                            # Remove apenas ESTA linha específica da base toda
                            df_ajustado = df_completo[df_completo['ID_Movimentacao'] != row['ID_Movimentacao']]
                            if salvar_dados(df_ajustado, "db_movimentacoes", modo='overwrite'):
                                st.warning(f"Item '{row['Nome_Produto']}' excluído da nota.")
                                st.rerun()

                if st.button("💾 SALVAR ALTERAÇÕES DE QUANTIDADE", type="primary", use_container_width=True):
                    df_completo = carregar_dados("db_movimentacoes")
                    for idx, row in itens.reset_index().iterrows():
                        nova_val = st.session_state[f"fix_q_{idx}_{row['ID_Movimentacao']}"]
                        df_completo.loc[df_completo['ID_Movimentacao'] == row['ID_Movimentacao'], 'Quantidade'] = nova_val
                    
                    if salvar_dados(df_completo, "db_movimentacoes", modo='overwrite'):
                        st.success("Quantidades atualizadas!")
                        st.rerun()
        else:
            st.info("Nada para corrigir.")

    # --- 4. REGISTRAR USO (CONSUMO) ---
    elif menu == "🍳 Registrar Uso (Consumo)":
        st.subheader("🍳 Registro de Baixa Diária")
        with st.form("f_uso", clear_on_submit=True):
            c1, c2 = st.columns(2)
            p_u = c1.selectbox("Produto", df_cat['Nome_Produto'].sort_values().tolist())
            q_u = c1.number_input("Quantidade", min_value=0.01)
            d_u = c2.date_input("Data", datetime.now(), format="DD/MM/YYYY")
            o_u = c2.text_input("Observação")
            
            if st.form_submit_button("Confirmar Saída", use_container_width=True):
                id_p = df_cat[df_cat['Nome_Produto'] == p_u]['ID_Produto'].values[0]
                df_s = pd.DataFrame([[f"SAI-{datetime.now().strftime('%y%m%d%H%M%S')}", d_u.strftime('%d/%m/%Y'), id_escola, "SAÍDA", nome_escola, "CONSUMO INTERNO", id_p, q_u, user_data['email'], o_u]], 
                                    columns=['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','ID_Usuario','Documento_Ref'])
                if salvar_dados(df_s, "db_movimentacoes", modo='append'):
                    st.warning(f"Saída de {q_u} {p_u} registrada.")
                    st.rerun()

    # --- 5. CADASTRAR NOVO ITEM ---
    elif menu == "🍎 Cadastrar Novo Item":
        st.subheader("🍎 Novo Item da Agricultura Familiar")
        with st.form("f_new_cat"):
            c1, c2 = st.columns(2)
            id_p = c1.text_input("ID (Ex: AF-PRODUTO)")
            nm_p = c1.text_input("Nome")
            un_p = c2.selectbox("Unidade", ["Kg", "Unid", "Maço", "Pct", "Cx"])
            if st.form_submit_button("Adicionar ao Catálogo"):
                novo_p = pd.DataFrame([[id_p, nm_p, "Agricultura Familiar", un_p]], columns=['ID_Produto', 'Nome_Produto', 'Categoria', 'Unidade_Medida'])
                if salvar_dados(novo_p, "db_catalogo"):
                    st.success("Item adicionado!")
                    st.rerun()

    # --- 6. RELATÓRIOS E DOCUMENTOS (PDF E EXCEL OTIMIZADO) ---
    elif menu == "📜 Relatórios e Documentos":
        st.subheader("📜 Histórico e Documentos")
        df_m = carregar_dados("db_movimentacoes")
        df_m = df_m[df_m['ID_Escola'] == id_escola].copy()
        
        if not df_m.empty:
            df_m = pd.merge(df_m, df_cat[['ID_Produto', 'Nome_Produto', 'Unidade_Medida']], on='ID_Produto', how='left')
            df_m['DT_OBJ'] = pd.to_datetime(df_m['Data_Hora'], dayfirst=True, errors='coerce')
            
            with st.container(border=True):
                c1, c2 = st.columns(2)
                f_per = c1.selectbox("Período Rápido", ["Mês Atual", "Trimestral", "Anual", "Todo Histórico"])
                f_tipo = c2.multiselect("Filtrar por Tipo", ["ENTRADA", "SAÍDA", "TRANSFERÊNCIA"])

            # Exibição Agrupada Visual
            for (doc, data), group in df_m.sort_values('DT_OBJ', ascending=False).groupby(['Documento_Ref', 'Data_Hora'], sort=False):
                with st.container(border=True):
                    st.markdown(f"📄 **Nota:** {doc} | 🗓️ **Data:** {data}")
                    st.table(group[['Nome_Produto', 'Quantidade', 'Unidade_Medida', 'Tipo_Fluxo']])

            st.divider()
            col1, col2 = st.columns(2)
            
            # Download Excel
            csv = df_m[['Data_Hora', 'Documento_Ref', 'Tipo_Fluxo', 'Nome_Produto', 'Quantidade', 'Unidade_Medida']].to_csv(index=False).encode('utf-8-sig')
            col1.download_button("📊 Baixar Excel Otimizado", csv, f"Relatorio_{id_escola}.csv", use_container_width=True)
            
            # Download PDF
            try:
                pdf_data = gerar_pdf_conferencia(df_m, nome_escola)
                col2.download_button("📄 Baixar PDF de Conferência", pdf_data, f"Conferencia_{id_escola}.pdf", "application/pdf", use_container_width=True)
            except Exception as e:
                col2.error("Instale 'fpdf' para gerar o PDF.")
        else:
            st.info("Histórico vazio.")
