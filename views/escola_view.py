import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from modules.database import carregar_dados, salvar_dados
from modules.logic import calcular_estoque_atual
import io

# Tenta carregar o FPDF de forma segura
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

    st.title(f"🏫 Portal da Escola: {nome_escola}")

    menu = st.sidebar.radio("Navegação Principal", [
        "🏠 Estoque Atual", 
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

    # --- 1. ESTOQUE ATUAL ---
    if menu == "🏠 Estoque Atual":
        st.subheader("📋 Saldo em Prateleira")
        saldo = calcular_estoque_atual(id_escola)
        if not saldo.empty:
            df_f = pd.merge(saldo, df_cat, on='ID_Produto', how='left')
            st.markdown("**📊 Visão Geral do Estoque**")
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

    # --- 2. RECEBER MATERIAIS (UX SEM CARA DE TABELA) ---
    elif menu == "📦 Receber Materiais":
        st.subheader("📦 Registrar Entrada de Material")
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            origem = c1.selectbox("De onde veio?", ["Agricultura Familiar", "SEMED", "Fornecedor"])
            doc_ref = c2.text_input("Nº da Nota / Documento")
            data_r = c3.date_input("Data da entrega", datetime.now(), format="DD/MM/YYYY")

        if 'lista_itens' not in st.session_state:
            st.session_state.lista_itens = [{'id': 0, 'prod': None, 'qtd': 0.0}]

        st.markdown("**Itens Recebidos:**")
        for i, item in enumerate(st.session_state.lista_itens):
            with st.container(border=True):
                col_p, col_q, col_d = st.columns([3, 1, 0.5])
                st.session_state.lista_itens[i]['prod'] = col_p.selectbox(
                    f"Escolha o Produto {i+1}", 
                    [None] + df_cat['Nome_Produto'].sort_values().tolist(), 
                    key=f"rec_p_{item['id']}"
                )
                st.session_state.lista_itens[i]['qtd'] = col_q.number_input(
                    "Quantidade", min_value=0.0, step=0.1, key=f"rec_q_{item['id']}"
                )
                if len(st.session_state.lista_itens) > 1:
                    if col_d.button("❌", key=f"rec_del_{item['id']}"):
                        st.session_state.lista_itens.pop(i)
                        st.rerun()

        if st.button("➕ Adicionar outro produto"):
            novo_id = st.session_state.lista_itens[-1]['id'] + 1
            st.session_state.lista_itens.append({'id': novo_id, 'prod': None, 'qtd': 0.0})
            st.rerun()

        st.divider()
        if st.button("✅ SALVAR RECEBIMENTO NO SISTEMA", type="primary", use_container_width=True):
            if not doc_ref:
                st.error("Por favor, preencha o número da nota!")
            else:
                lista_s = []
                # ID de transação único para evitar conflitos de salvamento
                t_id = datetime.now().strftime('%y%m%d%H%M%S')
                for idx, it in enumerate(st.session_state.lista_itens):
                    if it['prod'] and it['qtd'] > 0:
                        id_p = df_cat[df_cat['Nome_Produto'] == it['prod']]['ID_Produto'].values[0]
                        lista_s.append([
                            f"MOV-{t_id}-{idx}", data_r.strftime('%d/%m/%Y'), id_escola, 
                            "ENTRADA", origem, nome_escola, id_p, it['qtd'], 
                            user_data['email'], doc_ref
                        ])
                
                if lista_s:
                    df_novos = pd.DataFrame(lista_s, columns=['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','ID_Usuario','Documento_Ref'])
                    if salvar_dados(df_novos, "db_movimentacoes", modo='append'):
                        st.success("Recebimento registrado com sucesso!")
                        st.session_state.lista_itens = [{'id': 0, 'prod': None, 'qtd': 0.0}]
                        st.rerun()

    # --- 3. CORRIGIR LANÇAMENTO (RESOLUÇÃO DO TYPEERROR E EXCLUSÃO) ---
    elif menu == "✏️ Corrigir Lançamento":
        st.subheader("✏️ Ajustar ou Excluir Lançamentos")
        df_mov = carregar_dados("db_movimentacoes")
        minhas = df_mov[df_mov['ID_Escola'] == id_escola].copy()
        
        if not minhas.empty:
            minhas['Label'] = "Nota: " + minhas['Documento_Ref'] + " (" + minhas['Data_Hora'] + ")"
            opcoes = sorted(minhas['Label'].unique().tolist(), reverse=True)
            sel = st.selectbox("Selecione a Nota/Data para corrigir:", [None] + opcoes)
            
            if sel:
                doc_o = sel.split("Nota: ")[1].split(" (")[0]
                data_o = sel.split("(")[1].replace(")", "")
                
                # Itens desta nota específica
                itens_edicao = minhas[(minhas['Documento_Ref'] == doc_o) & (minhas['Data_Hora'] == data_o)]
                itens_edicao = pd.merge(itens_edicao, df_cat[['ID_Produto', 'Nome_Produto']], on='ID_Produto', how='left')

                st.warning(f"Você está editando a nota {doc_o}. Alterações serão gravadas apenas ao clicar no botão final.")
                
                novos_valores = []
                excluidos_ids = []

                for idx, row in itens_edicao.reset_index().iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 1, 1])
                        c1.markdown(f"**Item:** {row['Nome_Produto']}")
                        # Key única para evitar StreamlitDuplicateElementKey
                        val_q = c2.number_input("Nova Qtd", value=float(row['Quantidade']), key=f"fix_q_{idx}_{row['ID_Movimentacao']}")
                        
                        if c3.button("🗑️ Excluir Item", key=f"fix_d_{idx}_{row['ID_Movimentacao']}"):
                            excluidos_ids.append(row['ID_Movimentacao'])
                            st.toast(f"Item {row['Nome_Produto']} será removido.")

                        # Guardamos o dicionário da linha atualizada (sem o nome do produto temporário)
                        linha_up = row.to_dict()
                        linha_up['Quantidade'] = val_q
                        novos_valores.append(linha_up)

                if st.button("💾 SALVAR ALTERAÇÕES", type="primary", use_container_width=True):
                    df_full = carregar_dados("db_movimentacoes")
                    
                    # FILTRAGEM SEGURA: Remove os IDs antigos da nota e mantém o resto do banco
                    ids_originais = itens_edicao['ID_Movimentacao'].tolist()
                    df_restante = df_full[~df_full['ID_Movimentacao'].isin(ids_originais)]
                    
                    # Prepara os novos dados (removendo os que o usuário clicou em excluir)
                    df_novos_ajustados = pd.DataFrame(novos_valores)
                    df_novos_ajustados = df_novos_ajustados[~df_novos_ajustados['ID_Movimentacao'].isin(excluidos_ids)]
                    
                    # Limpeza de colunas extras do merge antes de salvar
                    df_novos_ajustados = df_novos_ajustados.drop(columns=['Nome_Produto', 'Label'], errors='ignore')
                    
                    # Concatena tudo e salva (Evita o TypeError por não usar .loc)
                    df_final_save = pd.concat([df_restante, df_novos_ajustados]).reset_index(drop=True)
                    
                    if salvar_dados(df_final_save, "db_movimentacoes", modo='overwrite'):
                        st.success("Nota atualizada com sucesso!")
                        st.rerun()
        else:
            st.info("Nenhum lançamento encontrado.")

    # --- 4. REGISTRAR USO (CONSUMO) ---
    elif menu == "🍳 Registrar Uso (Consumo)":
        st.subheader("🍳 Registro de Baixa Diária")
        with st.form("f_consumo_unidade", clear_on_submit=True):
            c1, c2 = st.columns(2)
            p_uso = c1.selectbox("Produto usado", df_cat['Nome_Produto'].sort_values().tolist())
            q_uso = c1.number_input("Quantidade", min_value=0.01)
            d_uso = c2.date_input("Data do uso", datetime.now(), format="DD/MM/YYYY")
            o_uso = c2.text_input("Observação/Finalidade")
            
            if st.form_submit_button("Confirmar Saída", use_container_width=True):
                id_p = df_cat[df_cat['Nome_Produto'] == p_uso]['ID_Produto'].values[0]
                df_saida = pd.DataFrame([[f"SAI-{datetime.now().strftime('%y%m%d%H%M%S')}", d_uso.strftime('%d/%m/%Y'), id_escola, "SAÍDA", nome_escola, "CONSUMO INTERNO", id_p, q_uso, user_data['email'], o_uso]], 
                                        columns=['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','ID_Usuario','Documento_Ref'])
                if salvar_dados(df_saida, "db_movimentacoes", modo='append'):
                    st.warning(f"Baixa de {q_uso} {p_uso} registrada.")
                    st.rerun()

    # --- 5. CADASTRAR NOVO ITEM ---
    elif menu == "🍎 Cadastrar Novo Item":
        st.subheader("🍎 Novo Item da Agricultura Familiar")
        with st.form("f_new_item"):
            c1, c2 = st.columns(2)
            id_p = c1.text_input("Código do Produto (Ex: AF-FRUTA)")
            nm_p = c1.text_input("Nome do Produto")
            un_p = c2.selectbox("Unidade de Medida", ["Kg", "Unid", "Maço", "Pct", "Cx"])
            if st.form_submit_button("Cadastrar no Catálogo"):
                df_n = pd.DataFrame([[id_p, nm_p, "Agricultura Familiar", un_p]], columns=['ID_Produto', 'Nome_Produto', 'Categoria', 'Unidade_Medida'])
                if salvar_dados(df_n, "db_catalogo"):
                    st.success("Item cadastrado com sucesso!")
                    st.rerun()

    # --- 6. RELATÓRIOS E DOCUMENTOS ---
    elif menu == "📜 Relatórios e Documentos":
        st.subheader("📜 Histórico de Movimentação")
        df_m = carregar_dados("db_movimentacoes")
        df_m = df_m[df_m['ID_Escola'] == id_escola].copy()
        
        if not df_m.empty:
            df_m = pd.merge(df_m, df_cat[['ID_Produto', 'Nome_Produto', 'Unidade_Medida']], on='ID_Produto', how='left')
            df_m['DT_OBJ'] = pd.to_datetime(df_m['Data_Hora'], dayfirst=True, errors='coerce')
            
            with st.expander("🔍 Filtros de Relatório"):
                f_periodo = st.selectbox("Período Rápido", ["Todo o Histórico", "Mês Atual", "Últimos 90 dias"])
                f_tipo = st.multiselect("Filtrar por Tipo", ["ENTRADA", "SAÍDA", "TRANSFERÊNCIA"])

            # Exibição Agrupada por Nota
            for (doc, data), group in df_m.sort_values('DT_OBJ', ascending=False).groupby(['Documento_Ref', 'Data_Hora'], sort=False):
                with st.container(border=True):
                    st.markdown(f"📄 **Documento:** {doc} | 🗓️ **Data:** {data}")
                    st.table(group[['Nome_Produto', 'Quantidade', 'Unidade_Medida', 'Tipo_Fluxo']])

            st.divider()
            col1, col2 = st.columns(2)
            
            # Excel Otimizado
            csv_data = df_m[['Data_Hora', 'Documento_Ref', 'Tipo_Fluxo', 'Nome_Produto', 'Quantidade', 'Unidade_Medida']].to_csv(index=False).encode('utf-8-sig')
            col1.download_button("📊 Baixar Excel para Conferência", csv_data, f"Estoque_{id_escola}.csv", use_container_width=True)
            
            # PDF (Botão de Download Real)
            if FPDF is not None:
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", 'B', 14)
                pdf.cell(190, 10, f"Relatorio de Estoque - {nome_escola}", ln=True, align='C')
                pdf.ln(5)
                pdf.set_font("Arial", 'B', 10)
                pdf.cell(30, 8, "Data", 1); pdf.cell(30, 8, "Nota", 1); pdf.cell(80, 8, "Produto", 1); pdf.cell(20, 8, "Qtd", 1); pdf.cell(30, 8, "Tipo", 1); pdf.ln()
                pdf.set_font("Arial", '', 8)
                for _, r in df_m.iterrows():
                    pdf.cell(30, 7, str(r['Data_Hora']), 1); pdf.cell(30, 7, str(r['Documento_Ref']), 1); pdf.cell(80, 7, str(r['Nome_Produto'])[:40], 1); pdf.cell(20, 7, str(r['Quantidade']), 1); pdf.cell(30, 7, str(r['Tipo_Fluxo']), 1); pdf.ln()
                
                pdf_bytes = pdf.output(dest='S').encode('latin-1')
                col2.download_button("📄 Baixar PDF de Impressão", pdf_bytes, f"Relatorio_{id_escola}.pdf", "application/pdf", use_container_width=True)
            else:
                col2.warning("PDF indisponível (Instale 'fpdf' no requirements.txt)")
        else:
            st.info("Histórico vazio.")
