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

    st.title(f"🏫 Portal da Escola: {nome_escola}")

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
        saldo = calcular_estoque_atual(id_escola)
        if not saldo.empty:
            df_f = pd.merge(saldo, df_cat, on='ID_Produto', how='left')
            st.markdown("**📊 Visão Geral**")
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
                if salvar_dados(pd.DataFrame(lista_s, columns=['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','ID_Usuario','Documento_Ref']), "db_movimentacoes", modo='append'):
                    st.success("Recebimento salvo!")
                    st.session_state.lista_itens = [{'id': 0, 'prod': None, 'qtd': 0.0}]
                    st.rerun()

    # --- 3. CORRIGIR LANÇAMENTO (COM ADIÇÃO DE ITENS E TRAVA DE SEGURANÇA) ---
    elif menu == "✏️ Corrigir/Adicionar em Nota":
        st.subheader("✏️ Edição Avançada de Recebimento")
        df_mov = carregar_dados("db_movimentacoes")
        minhas = df_mov[df_mov['ID_Escola'] == id_escola].copy()
        
        if not minhas.empty:
            minhas['Label'] = "Nota: " + minhas['Documento_Ref'] + " (" + minhas['Data_Hora'] + ")"
            sel = st.selectbox("Selecione o Documento para Alterar:", [None] + sorted(minhas['Label'].unique().tolist(), reverse=True))
            
            if sel:
                doc_o = sel.split("Nota: ")[1].split(" (")[0]
                data_o = sel.split("(")[1].replace(")", "")
                
                # Itens atuais da nota
                itens_edicao = minhas[(minhas['Documento_Ref'] == doc_o) & (minhas['Data_Hora'] == data_o)]
                itens_edicao = pd.merge(itens_edicao, df_cat[['ID_Produto', 'Nome_Produto']], on='ID_Produto', how='left')

                st.info(f"Você está editando a Nota: {doc_o}")

                # --- TRAVA DE SEGURANÇA PARA EXCLUSÃO ---
                trava_exclusao = st.sidebar.checkbox("🔓 Habilitar Exclusão de Itens", help="Marque para permitir apagar registros permanentemente.")

                novos_valores = []
                excluidos_ids = []

                # Listagem para Edição e Exclusão
                for idx, row in itens_edicao.reset_index().iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 1, 1])
                        c1.markdown(f"**Item:** {row['Nome_Produto']}")
                        val_q = c2.number_input("Qtd", value=float(row['Quantidade']), key=f"fix_q_{idx}_{row['ID_Movimentacao']}")
                        
                        if trava_exclusao:
                            if c3.button("🗑️ Excluir", key=f"fix_d_{idx}_{row['ID_Movimentacao']}", type="secondary"):
                                excluidos_ids.append(row['ID_Movimentacao'])
                                st.toast(f"Item {row['Nome_Produto']} marcado para remoção.")
                        else:
                            c3.write("🔒 Bloqueado")

                        l_up = row.to_dict()
                        l_up['Quantidade'] = val_q
                        novos_valores.append(l_up)

                # --- FUNCIONALIDADE: ADICIONAR NOVO PRODUTO NA MESMA NOTA ---
                with st.expander("➕ Adicionar novo produto a esta nota"):
                    new_p = st.selectbox("Selecione o Produto para Adicionar", [None] + df_cat['Nome_Produto'].sort_values().tolist(), key="add_p_nota")
                    new_q = st.number_input("Quantidade do novo item", min_value=0.0, key="add_q_nota")
                    if st.button("Inserir Produto na Nota"):
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
                            df_final_add = pd.concat([df_full, pd.DataFrame([nova_linha])])
                            if salvar_dados(df_final_add, "db_movimentacoes", modo='overwrite'):
                                st.success(f"{new_p} adicionado à nota {doc_o}!")
                                st.rerun()

                st.divider()
                if st.button("💾 SALVAR TODAS AS ALTERAÇÕES", type="primary", use_container_width=True):
                    df_full = carregar_dados("db_movimentacoes")
                    ids_originais = itens_edicao['ID_Movimentacao'].tolist()
                    df_restante = df_full[~df_full['ID_Movimentacao'].isin(ids_originais)]
                    
                    df_novos_ajustados = pd.DataFrame(novos_valores)
                    df_novos_ajustados = df_novos_ajustados[~df_novos_ajustados['ID_Movimentacao'].isin(excluidos_ids)]
                    df_novos_ajustados = df_novos_ajustados.drop(columns=['Nome_Produto', 'Label'], errors='ignore')
                    
                    df_final_save = pd.concat([df_restante, df_novos_ajustados]).reset_index(drop=True)
                    if salvar_dados(df_final_save, "db_movimentacoes", modo='overwrite'):
                        st.success("Nota atualizada!")
                        st.rerun()
        else:
            st.info("Nenhum lançamento.")

    # --- 6. RELATÓRIOS OFICIAIS (AGRUPAMENTO POR NOTA E DADOS DO RESPONSÁVEL) ---
    elif menu == "📜 Relatórios Oficiais":
        st.subheader("📜 Histórico Consolidado da Unidade")
        df_m = carregar_dados("db_movimentacoes")
        df_m = df_m[df_m['ID_Escola'] == id_escola].copy()
        
        if not df_m.empty:
            df_m = pd.merge(df_m, df_cat[['ID_Produto', 'Nome_Produto', 'Unidade_Medida']], on='ID_Produto', how='left')
            df_m['DT_OBJ'] = pd.to_datetime(df_m['Data_Hora'], dayfirst=True, errors='coerce')
            
            with st.container(border=True):
                st.markdown("**🔍 Filtros e Agrupamento**")
                c1, c2 = st.columns(2)
                f_per = c1.selectbox("Período", ["Mês Atual", "Todo o Histórico"])
                f_tipo = c2.multiselect("Tipo de Fluxo", ["ENTRADA", "SAÍDA", "TRANSFERÊNCIA"])
                
                if f_tipo: df_m = df_m[df_m['Tipo_Fluxo'].isin(f_tipo)]

            st.write(f"### Recebimentos da Unidade: {nome_escola}")
            
            # --- AGRUPAMENTO DEFINITIVO POR NOTA ---
            # Ordenamos por data para que o agrupamento faça sentido visual
            df_m = df_m.sort_values('DT_OBJ', ascending=False)
            grupos = df_m.groupby(['Documento_Ref', 'Data_Hora', 'Origem', 'ID_Usuario'], sort=False)
            
            for (doc, data, ori, resp), group in grupos:
                with st.container(border=True):
                    st.markdown(f"📄 **Documento/Nota:** `{doc}` | 🗓️ **Data:** {data}")
                    st.markdown(f"📍 **Origem:** {ori} | 👤 **Responsável:** `{resp}`")
                    
                    # Exibe os itens dentro do bloco da nota como uma tabela limpa
                    st.table(group[['Nome_Produto', 'Quantidade', 'Unidade_Medida', 'Tipo_Fluxo']])

            st.divider()
            c1, c2 = st.columns(2)
            # Excel
            csv_data = df_m[['Data_Hora', 'Documento_Ref', 'Origem', 'ID_Usuario', 'Nome_Produto', 'Quantidade', 'Unidade_Medida']].to_csv(index=False).encode('utf-8-sig')
            c1.download_button("📊 Baixar Excel Otimizado", csv_data, f"Relatorio_{id_escola}.csv", use_container_width=True)
            
            # PDF (Botão de Download)
            if FPDF is not None:
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(190, 10, f"Relatorio SEMED - {nome_escola}", ln=True, align='C')
                pdf.set_font("Arial", '', 8)
                for _, r in df_m.iterrows():
                    pdf.cell(30, 7, str(r['Data_Hora']), 1); pdf.cell(30, 7, str(r['Documento_Ref']), 1); pdf.cell(70, 7, str(r['Nome_Produto'])[:35], 1); pdf.cell(20, 7, str(r['Quantidade']), 1); pdf.cell(40, 7, str(r['ID_Usuario'])[:30], 1); pdf.ln()
                c2.download_button("📄 Baixar PDF de Conferência", pdf.output(dest='S').encode('latin-1'), f"Relatorio_{id_escola}.pdf", "application/pdf", use_container_width=True)
        else:
            st.info("Histórico vazio.")
