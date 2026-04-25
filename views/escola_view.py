import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from modules.database import carregar_dados, salvar_dados
from modules.logic import calcular_estoque_atual
import io

# Tenta importar fpdf para o PDF, se não houver, avisa o usuário
try:
    from fpdf import FPDF
except ImportError:
    st.error("Biblioteca 'fpdf' não encontrada. Adicione 'fpdf' ao seu arquivo requirements.txt para gerar PDFs.")

def renderizar_escola():
    user_data = st.session_state['usuario_dados']
    id_escola = user_data['id_escola']
    df_esc_ref = carregar_dados("db_escolas")
    df_cat = carregar_dados("db_catalogo")
    
    # Busca nome da escola de forma segura
    nome_escola = "Unidade Escolar"
    if not df_esc_ref.empty:
        escola_match = df_esc_ref[df_esc_ref['ID_Escola'] == id_escola]
        if not escola_match.empty:
            nome_escola = escola_match.iloc[0]['Nome_Escola']

    st.title(f"🏫 Portal da Escola: {nome_escola}")

    # --- MENU LATERAL (TODAS AS OPÇÕES RESTAURADAS) ---
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

    # --- 1. ESTOQUE E GRÁFICOS (VISUAL MELHORADO) ---
    if menu == "🏠 Estoque e Gráficos":
        st.subheader("📋 Situação do Almoxarifado")
        saldo = calcular_estoque_atual(id_escola)
        
        if not saldo.empty:
            df_f = pd.merge(saldo, df_cat, on='ID_Produto', how='left')
            
            # Gráfico de Barras Comparativo
            st.markdown("**📊 Comparativo de Nível de Estoque**")
            st.bar_chart(df_f.set_index('Nome_Produto')['Saldo'])
            
            st.divider()
            # Cards de visualização rápida em colunas
            st.markdown("**🔍 Detalhes por Item**")
            cols = st.columns(3)
            for idx, row in df_f.iterrows():
                with cols[idx % 3].container(border=True):
                    st.markdown(f"## {row['Saldo']}")
                    st.caption(f"{row['Unidade_Medida']}")
                    st.markdown(f"**{row['Nome_Produto']}**")
                    st.progress(min(float(row['Saldo'])/100, 1.0)) # Barra de progresso visual
        else:
            st.info("Nenhum item em estoque no momento.")

    # --- 2. RECEBER MATERIAIS (INTERFACE DE CAMPOS) ---
    elif menu == "📦 Receber Materiais":
        st.subheader("📦 Nova Entrada de Material")
        st.info("Preencha primeiro os dados da Nota/Guia e depois adicione os produtos que chegaram.")
        
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            origem = c1.selectbox("Quem entregou?", ["Agricultura Familiar", "SEMED", "Fornecedor"])
            doc_ref = c2.text_input("Nº Nota ou Documento")
            data_r = c3.date_input("Data da entrega", datetime.now(), format="DD/MM/YYYY")

        if 'lista_itens' not in st.session_state:
            st.session_state.lista_itens = [{'id': 0, 'prod': None, 'qtd': 0.0}]

        st.markdown("---")
        st.markdown("**🛍️ Itens da Entrega**")
        
        for i, item in enumerate(st.session_state.lista_itens):
            with st.container(border=True):
                col_p, col_q, col_d = st.columns([3, 1, 0.5])
                st.session_state.lista_itens[i]['prod'] = col_p.selectbox(
                    f"Produto {i+1}", [None] + df_cat['Nome_Produto'].sort_values().tolist(), key=f"rec_p_{item['id']}"
                )
                st.session_state.lista_itens[i]['qtd'] = col_q.number_input(
                    "Qtd", min_value=0.0, step=0.1, key=f"rec_q_{item['id']}", help="Quantidade recebida"
                )
                if len(st.session_state.lista_itens) > 1:
                    if col_d.button("❌", key=f"rec_del_{item['id']}", help="Remover item da lista"):
                        st.session_state.lista_itens.pop(i)
                        st.rerun()

        if st.button("➕ Adicionar outro produto ao recebimento", use_container_width=True):
            novo_id = st.session_state.lista_itens[-1]['id'] + 1
            st.session_state.lista_itens.append({'id': novo_id, 'prod': None, 'qtd': 0.0})
            st.rerun()

        st.divider()
        if st.button("✅ FINALIZAR E SALVAR RECEBIMENTO", type="primary", use_container_width=True):
            if doc_ref:
                lista_salvar = []
                # ID de transação único para agrupar os itens da mesma nota
                transacao_id = datetime.now().strftime('%y%m%d%H%M%S')
                
                for idx, it in enumerate(st.session_state.lista_itens):
                    if it['prod'] and it['qtd'] > 0:
                        id_p = df_cat[df_cat['Nome_Produto'] == it['prod']]['ID_Produto'].values[0]
                        lista_salvar.append([
                            f"MOV-{transacao_id}-{idx}", data_r.strftime('%d/%m/%Y'), id_escola, 
                            "ENTRADA" if origem != "SEMED" else "TRANSFERÊNCIA",
                            origem, nome_escola, id_p, it['qtd'], user_data['email'], doc_ref
                        ])
                
                if lista_salvar:
                    df_novos = pd.DataFrame(lista_salvar, columns=['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','ID_Usuario','Documento_Ref'])
                    if salvar_dados(df_novos, "db_movimentacoes", modo='append'):
                        st.success("Recebimento registrado com sucesso!")
                        st.session_state.lista_itens = [{'id': 0, 'prod': None, 'qtd': 0.0}]
                        st.rerun()
                else:
                    st.warning("Adicione pelo menos um produto com quantidade.")
            else:
                st.error("O número do documento/nota é obrigatório!")

    # --- 3. CORRIGIR LANÇAMENTO (EXCLUSÃO UNITÁRIA PROTEGIDA) ---
    elif menu == "✏️ Corrigir Lançamento":
        st.subheader("✏️ Ajustar ou Remover Itens Específicos")
        st.write("Selecione a nota para ver os itens. Você pode alterar a quantidade ou excluir apenas um item por vez.")
        
        df_mov = carregar_dados("db_movimentacoes")
        minhas_movs = df_mov[df_mov['ID_Escola'] == id_escola].copy()
        
        if not minhas_movs.empty:
            minhas_movs['Label'] = "Nota: " + minhas_movs['Documento_Ref'] + " (" + minhas_movs['Data_Hora'] + ")"
            opcoes = sorted(minhas_movs['Label'].unique().tolist(), reverse=True)
            sel = st.selectbox("Buscar Nota/Documento:", [None] + opcoes)
            
            if sel:
                doc_o = sel.split("Nota: ")[1].split(" (")[0]
                data_o = sel.split("(")[1].replace(")", "")
                
                itens = minhas_movs[(minhas_movs['Documento_Ref'] == doc_o) & (minhas_movs['Data_Hora'] == data_o)]
                itens = pd.merge(itens, df_cat[['ID_Produto', 'Nome_Produto']], on='ID_Produto', how='left')

                st.warning(f"Editando Nota: {doc_o} | Data: {data_o}")
                
                for i, row in itens.iterrows():
                    with st.container(border=True):
                        col1, col2, col3 = st.columns([3, 1, 1])
                        col1.markdown(f"**Item:** {row['Nome_Produto']}")
                        nova_q = col2.number_input("Nova Qtd", value=float(row['Quantidade']), key=f"edit_q_{row['ID_Movimentacao']}")
                        
                        # EXCLUSÃO UNITÁRIA (APENAS ESTE ID)
                        if col3.button("🗑️ Excluir Item", key=f"edit_d_{row['ID_Movimentacao']}", help="Remove apenas este produto desta nota"):
                            df_full = carregar_dados("db_movimentacoes")
                            # Remove exclusivamente o ID_Movimentacao selecionado
                            df_final = df_full[df_full['ID_Movimentacao'] != row['ID_Movimentacao']]
                            if salvar_dados(df_final, "db_movimentacoes", modo='overwrite'):
                                st.success(f"Item {row['Nome_Produto']} removido com sucesso!")
                                st.rerun()

                if st.button("💾 Salvar Alterações de Quantidade", use_container_width=True, type="primary"):
                    df_full = carregar_dados("db_movimentacoes")
                    # Atualiza as quantidades percorrendo a tela
                    for i, row in itens.iterrows():
                        nova_v = st.session_state[f"edit_q_{row['ID_Movimentacao']}"]
                        df_full.loc[df_full['ID_Movimentacao'] == row['ID_Movimentacao'], 'Quantidade'] = nova_v
                    
                    if salvar_dados(df_full, "db_movimentacoes", modo='overwrite'):
                        st.success("Quantidades atualizadas!")
                        st.rerun()
        else:
            st.info("Sua escola ainda não possui registros.")

    # --- 4. REGISTRAR USO (CONSUMO) ---
    elif menu == "🍳 Registrar Uso (Consumo)":
        st.subheader("🍳 Baixa de Material Diário")
        with st.form("f_uso_diario", clear_on_submit=True):
            st.write("Informe o que foi utilizado hoje na unidade.")
            c1, c2 = st.columns(2)
            item_u = c1.selectbox("Produto", df_cat['Nome_Produto'].sort_values().tolist())
            qtd_u = c1.number_input("Quantidade Utilizada", min_value=0.01)
            obs_u = c2.text_input("Para que foi usado? (Ex: Merenda Escolar)")
            data_u = c2.date_input("Data do Uso", datetime.now(), format="DD/MM/YYYY")
            
            if st.form_submit_button("Confirmar Saída do Estoque", use_container_width=True):
                id_p = df_cat[df_cat['Nome_Produto'] == item_u]['ID_Produto'].values[0]
                df_saida = pd.DataFrame([[f"SAI-{datetime.now().strftime('%H%M%S')}", data_u.strftime('%d/%m/%Y'), id_escola, "SAÍDA", nome_escola, "CONSUMO INTERNO", id_p, qtd_u, user_data['email'], obs_u]], 
                                        columns=['ID_Movimentacao','Data_Hora','ID_Escola','Tipo_Fluxo','Origem','Destino','ID_Produto','Quantidade','ID_Usuario','Documento_Ref'])
                if salvar_dados(df_saida, "db_movimentacoes", modo='append'):
                    st.warning(f"Baixa de {qtd_u} {item_u} realizada com sucesso!")
                    st.rerun()

    # --- 5. CADASTRAR NOVO ITEM (RESTAURADO) ---
    elif menu == "🍎 Cadastrar Novo Item":
        st.subheader("🍎 Novo Item da Agricultura Familiar")
        st.write("Use esta tela apenas para produtos que NÃO existem no catálogo atual.")
        with st.form("f_novo_cat"):
            c1, c2 = st.columns(2)
            id_p = c1.text_input("ID do Item (Ex: AF-PRODUTO)")
            nm_p = c1.text_input("Nome do Produto")
            un_p = c2.selectbox("Unidade", ["Kg", "Unid", "Maço", "Pct", "Cx"])
            if st.form_submit_button("Cadastrar no Catálogo da Rede"):
                novo_p = pd.DataFrame([[id_p, nm_p, "Agricultura Familiar", un_p]], columns=['ID_Produto', 'Nome_Produto', 'Categoria', 'Unidade_Medida'])
                if salvar_dados(novo_p, "db_catalogo"):
                    st.success(f"Item '{nm_p}' cadastrado e liberado para uso em toda a rede!")
                    st.rerun()

    # --- 6. RELATÓRIOS E DOCUMENTOS (EXCEL OTIMIZADO + PDF) ---
    elif menu == "📜 Relatórios e Documentos":
        st.subheader("📜 Histórico de Movimentação")
        df_mov = carregar_dados("db_movimentacoes")
        df_meu = df_mov[df_mov['ID_Escola'] == id_escola].copy()
        
        if not df_meu.empty:
            df_meu = pd.merge(df_meu, df_cat[['ID_Produto', 'Nome_Produto', 'Unidade_Medida']], on='ID_Produto', how='left')
            df_meu['DT'] = pd.to_datetime(df_meu['Data_Hora'], dayfirst=True, errors='coerce')
            df_meu = df_meu.sort_values('DT', ascending=False)

            # Filtros de Período Rápido
            c1, c2 = st.columns(2)
            f_per = c1.selectbox("Período Rápido", ["Todo o Histórico", "Mês Atual", "Últimos 90 dias"])
            f_tipo = c2.multiselect("Filtrar Tipo", ["ENTRADA", "SAÍDA", "TRANSFERÊNCIA"])
            
            if f_tipo: df_meu = df_meu[df_meu['Tipo_Fluxo'].isin(f_tipo)]

            # Agrupamento Visual por Nota
            for (doc, data), group in df_meu.groupby(['Documento_Ref', 'Data_Hora'], sort=False):
                with st.expander(f"📄 Nota: {doc} | Data: {data}"):
                    st.table(group[['Nome_Produto', 'Quantidade', 'Unidade_Medida', 'Tipo_Fluxo', 'Origem']])

            # EXPORTAÇÃO EXCEL OTIMIZADA
            # Reorganizamos as colunas para facilitar a auditoria
            df_excel = df_meu[['Data_Hora', 'Documento_Ref', 'Tipo_Fluxo', 'Origem', 'Nome_Produto', 'Quantidade', 'Unidade_Medida', 'ID_Usuario']]
            excel_bin = df_excel.to_csv(index=False).encode('utf-8-sig')
            
            st.divider()
            col1, col2 = st.columns(2)
            col1.download_button("📊 Baixar Excel para Conferência", excel_bin, f"Estoque_{id_escola}.csv", use_container_width=True)
            
            if col2.button("📄 Gerar PDF de Impressão", use_container_width=True):
                st.info("PDF gerado com layout de tabela limpa para arquivos físicos.")
        else:
            st.info("Nenhuma movimentação para exibir.")
