import streamlit as st
import psycopg2
import pandas as pd
import calendar
from datetime import datetime, date, timedelta
from calendar import monthrange

# ==========================================
# CONFIGURAÇÃO DA PÁGINA WEB
# ==========================================
st.set_page_config(page_title="Gestão de Escala e Férias", page_icon="📅", layout="wide")
calendar.setfirstweekday(calendar.SUNDAY)

# ⚠️ COLE AQUI A SUA CONNECTION STRING DO SUPABASE ⚠️
DB_URI = "postgresql://postgres.onrosedryqrtsvswydxv:Q2n&wripu7nW-Nk@aws-1-sa-east-1.pooler.supabase.com:5432/postgres"

# ==========================================
# CONEXÃO COM O BANCO DE DADOS (PostgreSQL)
# ==========================================
@st.cache_resource
def init_connection():
    return psycopg2.connect(DB_URI)

try:
    conn = init_connection()
    conn.autocommit = True
    cursor = conn.cursor()
except Exception as e:
    st.error(f"🚨 Erro de Conexão com o Supabase. Verifique a sua DB_URI. Detalhe: {e}")
    st.stop()

# ==========================================
# SISTEMA DE LOGIN (SEGURANÇA DA NUVEM)
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔒 Acesso Restrito - TI Camarotti")
    st.write("Por favor, insira a senha corporativa para gerenciar as escalas.")
    senha = st.text_input("Senha de Acesso", type="password")
    if st.button("Entrar"):
        if senha == "camarotti2026": # <-- ALTERE A SENHA AQUI
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("Senha incorreta!")
    st.stop()

# ==========================================
# MOTORES DE CÁLCULO E LÓGICA
# ==========================================
def get_saldos(colab_id):
    cursor.execute("SELECT dias_pendentes, saldo_bh FROM colaboradores WHERE id=%s", (colab_id,))
    res = cursor.fetchone()
    if not res: return 0, 0.0, 0, 0.0, 0, 0, 0.0
    
    dias_db = int(res[0])
    bh_db = float(res[1])
    hoje = datetime.now()
    f_efetivas, f_oficial, f_bh = 0, 0, 0.0

    cursor.execute("SELECT tipo, data_inicio, numero_dias, valor_descontado FROM lancamentos WHERE colaborador_id=%s", (colab_id,))
    for tipo, d_ini_str, num_dias, v_desc in cursor.fetchall():
        try:
            dt_ini = datetime.strptime(d_ini_str, "%d/%m/%Y")
            if dt_ini.year > hoje.year or (dt_ini.year == hoje.year and dt_ini.month > hoje.month):
                if tipo == "Férias (Efetivas)": f_efetivas += num_dias
                elif tipo == "Férias (Oficial)": f_oficial += num_dias
                elif tipo == "Folga BH": f_bh += float(v_desc)
        except: pass

    dias_atual = dias_db + f_efetivas - f_oficial
    bh_atual = bh_db + f_bh
    return dias_atual, bh_atual, dias_db, bh_db, f_efetivas, f_oficial, f_bh

def obter_datas_ocupadas(colaborador_id):
    cursor.execute("SELECT data_inicio, data_fim FROM lancamentos WHERE colaborador_id = %s AND tipo != 'Férias (Oficial)'", (colaborador_id,))
    lancamentos = cursor.fetchall()
    datas_ocupadas = set()
    for d_ini_str, d_fim_str in lancamentos:
        try:
            d_ini = datetime.strptime(d_ini_str, "%d/%m/%Y")
            d_fim = datetime.strptime(d_fim_str, "%d/%m/%Y")
            atual = d_ini
            while atual <= d_fim:
                datas_ocupadas.add(atual.strftime("%d/%m/%Y"))
                atual += timedelta(days=1)
        except: pass
    return datas_ocupadas

# ==========================================
# MENU DE NAVEGAÇÃO LATERAL
# ==========================================
st.sidebar.title("📅 Gestão de Escala")
st.sidebar.markdown("---")
menu = st.sidebar.radio("Selecione o Módulo:", [
    "📊 Dashboard Interativo", 
    "👥 Gestão de Equipe", 
    "✈️ Lançamentos (Férias e Folgas)",
    "🌴 Gerir Feriados"
])

# ==========================================
# MÓDULO 1: DASHBOARD
# ==========================================
if menu == "📊 Dashboard Interativo":
    st.header("Dashboard da Equipe")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    ano_atual = datetime.now().year
    mes_atual = datetime.now().month
    
    with col1:
        ano_selecionado = st.selectbox("Ano", range(ano_atual - 2, ano_atual + 3), index=2)
    with col2:
        meses = ["Resumo Anual", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        mes_selecionado = st.selectbox("Mês / Visão", meses, index=mes_atual)
    with col3:
        st.markdown("**Filtros:**")
        mostrar_presencial = st.checkbox("Mostrar Presencial", value=False)
    
    st.markdown("---")
    
    # Cache de Lançamentos
    cursor.execute("SELECT c.nome, l.tipo, l.data_inicio, l.data_fim FROM lancamentos l JOIN colaboradores c ON l.colaborador_id = c.id WHERE c.ativo = 1")
    todos_lancamentos = cursor.fetchall()
    
    cursor.execute("SELECT data_feriado, descricao FROM feriados")
    feriados = {linha[0]: linha[1] for linha in cursor.fetchall()}

    if mes_selecionado == "Resumo Anual":
        st.subheader(f"Resumo de Férias do Ano - {ano_selecionado}")
        dados_resumo = []
        for nome, tipo, d_ini, d_fim in todos_lancamentos:
            if "Férias" in tipo:
                try:
                    dt_ini = datetime.strptime(d_ini, "%d/%m/%Y")
                    dt_fim = datetime.strptime(d_fim, "%d/%m/%Y")
                    if dt_ini.year == ano_selecionado or dt_fim.year == ano_selecionado:
                        dias = (dt_fim - dt_ini).days + 1
                        dados_resumo.append({"Colaborador": nome, "Tipo": tipo, "Início": d_ini, "Fim": d_fim, "Dias": dias, "SortDate": dt_ini})
                except: pass
        
        if dados_resumo:
            df_resumo = pd.DataFrame(dados_resumo).sort_values(by="SortDate").drop(columns=["SortDate"])
            st.dataframe(df_resumo, use_container_width=True)
        else:
            st.info("Nenhuma férias programada para este ano.")

    else:
        # CONSTRUTOR DO CALENDÁRIO VISUAL EM HTML (Muito melhor no Streamlit)
        mes_num = meses.index(mes_selecionado)
        cal = calendar.monthcalendar(ano_selecionado, mes_num)
        
        eventos_mes = {d: [] for d in range(1, 32)}
        for nome, tipo, d_ini_str, d_fim_str in todos_lancamentos:
            if tipo == "Presencial" and not mostrar_presencial: continue
            try:
                dt_ini = datetime.strptime(d_ini_str, "%d/%m/%Y").date()
                dt_fim = datetime.strptime(d_fim_str, "%d/%m/%Y").date()
                atual = dt_ini
                while atual <= dt_fim:
                    if atual.month == mes_num and atual.year == ano_selecionado:
                        eventos_mes[atual.day].append((nome.split()[0], tipo))
                    atual += timedelta(days=1)
            except: pass

        cores = {"Presencial": "#33cc66", "Férias (Efetivas)": "#ff9933", "Férias (Oficial)": "#ff4d4d", "Folga BH": "#66a3ff"}
        
        html_cal = "<table style='width:100%; border-collapse: collapse; text-align:center; font-family:sans-serif;'>"
        html_cal += "<tr style='background-color:#1f538d; color:white;'><th>Dom</th><th>Seg</th><th>Ter</th><th>Qua</th><th>Qui</th><th>Sex</th><th>Sáb</th></tr>"
        
        for semana in cal:
            html_cal += "<tr>"
            for col, dia in enumerate(semana):
                if dia == 0:
                    html_cal += "<td style='border: 1px solid #ddd; background-color:#f0f2f6; padding:10px;'></td>"
                else:
                    data_str = f"{dia:02d}/{mes_num:02d}/{ano_selecionado}"
                    bg_color = "#ffffff" if (col != 0 and col != 6) else "#f9f9f9"
                    
                    eventos_html = ""
                    if data_str in feriados:
                        bg_color = "#fff0cc"
                        eventos_html += f"<div style='color:#cc8800; font-size:12px; font-weight:bold;'>★ {feriados[data_str]}</div>"
                    
                    for ev_nome, ev_tipo in eventos_mes[dia]:
                        cor_txt = cores.get(ev_tipo, "#000")
                        eventos_html += f"<div style='color:{cor_txt}; font-size:12px; font-weight:bold; margin-top:2px;'>■ {ev_nome}</div>"
                    
                    html_cal += f"<td style='border: 1px solid #ddd; background-color:{bg_color}; padding:10px; vertical-align:top; min-height:80px; width:14%;'>"
                    html_cal += f"<div style='font-size:16px; font-weight:bold; color:#555; text-align:right;'>{dia}</div>"
                    html_cal += eventos_html
                    html_cal += "</td>"
            html_cal += "</tr>"
        html_cal += "</table>"
        
        st.markdown(html_cal, unsafe_allow_html=True)
        
        st.markdown("<br><small><b>Legenda:</b> <span style='color:#33cc66'>■ Presencial</span> | <span style='color:#ff9933'>■ Férias Efetivas</span> | <span style='color:#ff4d4d'>■ Férias Oficial</span> | <span style='color:#66a3ff'>■ Folga BH</span></small>", unsafe_allow_html=True)

# ==========================================
# MÓDULO 2: GESTÃO DE EQUIPE
# ==========================================
elif menu == "👥 Gestão de Equipe":
    st.header("Gestão de Colaboradores")
    
    cursor.execute("SELECT id, nome, ativo FROM colaboradores ORDER BY ativo DESC, nome ASC")
    colaboradores = cursor.fetchall()
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Equipe")
        lista_nomes = ["➕ Cadastrar Novo"] + [f"{c[1]} {'(Inativo)' if c[2]==0 else ''}" for c in colaboradores]
        escolha = st.radio("Selecione:", lista_nomes)
    
    with col2:
        if escolha == "➕ Cadastrar Novo":
            st.subheader("Novo Colaborador")
            with st.form("form_novo_colab"):
                nome = st.text_input("Nome Completo")
                funcao = st.text_input("Função")
                area = st.text_input("Área")
                admissao = st.date_input("Data de Admissão", format="DD/MM/YYYY")
                d_pendentes = st.number_input("Dias Pendentes (Saldo Inicial)", value=0, step=1)
                bh_inicial = st.number_input("Saldo Banco de Horas Inicial", value=0.0, step=0.5)
                
                if st.form_submit_button("💾 Salvar Colaborador", use_container_width=True):
                    try:
                        cursor.execute("INSERT INTO colaboradores (nome, funcao, area, admissao, dias_pendentes, saldo_bh) VALUES (%s, %s, %s, %s, %s, %s)", 
                                       (nome, funcao, area, admissao.strftime("%d/%m/%Y"), d_pendentes, bh_inicial))
                        st.success("Colaborador cadastrado!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")
        else:
            idx = lista_nomes.index(escolha) - 1
            colab_id = colaboradores[idx][0]
            
            cursor.execute("SELECT nome, funcao, area, admissao, ativo FROM colaboradores WHERE id=%s", (colab_id,))
            dados = cursor.fetchone()
            d_atual, b_atual, d_db, b_db, f_efe, f_ofic, f_bh = get_saldos(colab_id)
            
            st.subheader(f"Editando: {dados[0]}")
            
            st.info(f"**Saldo Atual (Neste mês):** {d_atual} dias pendentes | {b_atual}h no Banco")
            if f_efe > 0 or f_ofic > 0 or f_bh > 0:
                st.warning(f"📅 **Projetado (Futuro):** +{f_ofic}d (Assinar) | -{f_efe}d (Efetivas) | -{f_bh}h (Folga)")

            with st.form("form_edita_colab"):
                nome = st.text_input("Nome Completo", value=dados[0])
                funcao = st.text_input("Função", value=dados[1])
                area = st.text_input("Área", value=dados[2])
                d_pendentes = st.number_input("Dias Pendentes (Mês Atual)", value=int(d_atual), step=1)
                bh_atual_input = st.number_input("Saldo Banco de Horas (Mês Atual)", value=float(b_atual), step=0.5)
                
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    submit = st.form_submit_button("💾 Salvar Alterações", use_container_width=True)
                with col_btn2:
                    btn_status = "Arquivar" if dados[4] == 1 else "Reativar"
                    status_submit = st.form_submit_button(f"📦 {btn_status} Colaborador", use_container_width=True)

                if submit:
                    novo_d_db = d_pendentes - f_efe + f_ofic
                    novo_b_db = bh_atual_input - f_bh
                    cursor.execute("UPDATE colaboradores SET nome=%s, funcao=%s, area=%s, dias_pendentes=%s, saldo_bh=%s WHERE id=%s", 
                                   (nome, funcao, area, novo_d_db, novo_b_db, colab_id))
                    st.success("Atualizado!")
                    st.rerun()
                
                if status_submit:
                    novo_st = 0 if dados[4] == 1 else 1
                    cursor.execute("UPDATE colaboradores SET ativo=%s WHERE id=%s", (novo_st, colab_id))
                    st.rerun()

# ==========================================
# MÓDULO 3: LANÇAMENTOS 
# ==========================================
elif menu == "✈️ Lançamentos (Férias e Folgas)":
    st.header("Lançamentos Individuais")
    
    cursor.execute("SELECT id, nome FROM colaboradores WHERE ativo = 1 ORDER BY nome ASC")
    colabs = cursor.fetchall()
    
    if not colabs:
        st.warning("Cadastre um colaborador primeiro.")
        st.stop()
        
    colab_selecionado = st.selectbox("Selecione o Colaborador:", [c[1] for c in colabs])
    colab_id = [c[0] for c in colabs if c[1] == colab_selecionado][0]
    
    d_atual, b_atual, d_db, b_db, _, _, _ = get_saldos(colab_id)
    
    st.markdown(f"**Saldo Atual:** `{d_atual} dias` | Banco de Horas: `{b_atual}h`")
    
    # Botões na horizontal para melhor visualização
    tipo_lancamento = st.radio("O que deseja lançar?", ["Férias", "Presencial", "Folga BH"], horizontal=True)
    
    # ----------------------------------------------------
    # LÓGICA 1: FÉRIAS (Contínuas por Data Inicial/Final)
    # ----------------------------------------------------
    if tipo_lancamento == "Férias":
        with st.form("form_ferias"):
            acao_ferias = st.selectbox("Ação de Férias:", ["✍️ Assinar (Férias Oficial) -> ADICIONA Saldo", "🏖️ Efetivar (Férias Efetivas) -> DESCONTA Saldo"])
            tipo_bd = "Férias (Oficial)" if "Oficial" in acao_ferias else "Férias (Efetivas)"
            
            col1, col2 = st.columns(2)
            d_inicio = col1.date_input("Data de Início", format="DD/MM/YYYY")
            d_fim = col2.date_input("Data de Fim", format="DD/MM/YYYY")
            
            btn_lancar = st.form_submit_button("🚀 Gravar Férias", type="primary", use_container_width=True)
            
            if btn_lancar:
                if d_fim < d_inicio:
                    st.error("A data de fim não pode ser antes do início.")
                else:
                    qtd_dias = (d_fim - d_inicio).days + 1
                    
                    if tipo_bd == "Férias (Efetivas)" and (d_db - qtd_dias) < 0:
                        st.error(f"Saldo final insuficiente! Projetado: {d_db} dias. Tentativa: {qtd_dias} dias.")
                    else:
                        cursor.execute("INSERT INTO lancamentos (colaborador_id, tipo, data_inicio, data_fim, numero_dias, valor_descontado) VALUES (%s, %s, %s, %s, %s, %s)",
                                       (colab_id, tipo_bd, d_inicio.strftime("%d/%m/%Y"), d_fim.strftime("%d/%m/%Y"), qtd_dias, 0))
                        
                        if tipo_bd == "Férias (Oficial)":
                            cursor.execute("UPDATE colaboradores SET dias_pendentes = dias_pendentes + %s WHERE id = %s", (qtd_dias, colab_id))
                        elif tipo_bd == "Férias (Efetivas)":
                            cursor.execute("UPDATE colaboradores SET dias_pendentes = dias_pendentes - %s WHERE id = %s", (qtd_dias, colab_id))
                        
                        st.success("Férias lançadas com sucesso!")
                        st.rerun()

    # ----------------------------------------------------
    # LÓGICA 2: PRESENCIAL E FOLGA (Dias Picados via Calendário Lote)
    # ----------------------------------------------------
    else:
        st.markdown("---")
        st.markdown(f"### 📅 Selecionar Dias - {tipo_lancamento}")
        
        if tipo_lancamento == "Folga BH":
            horas_abater = st.number_input("Horas a abater por dia:", value=8.0, step=0.5)
            tipo_bd = "Folga BH"
        else:
            horas_abater = 0
            tipo_bd = "Presencial"
            
        with st.form("form_dias_lote"):
            col_m, col_a = st.columns(2)
            meses_lista = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
            mes_sel = col_m.selectbox("Mês Alvo", meses_lista, index=datetime.now().month - 1)
            ano_sel = col_a.number_input("Ano Alvo", value=datetime.now().year, step=1)
            
            st.write("Marque as caixinhas dos dias que deseja lançar abaixo:")
            mes_num = meses_lista.index(mes_sel) + 1
            cal_matriz = calendar.monthcalendar(ano_sel, mes_num)
            
            # Cabeçalho da grade visual
            dias_semana = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]
            cols_header = st.columns(7)
            for i, d in enumerate(dias_semana):
                cols_header[i].markdown(f"**{d}**")
                
            # Linhas da grade visual (O Calendário)
            dias_marcados = []
            for semana in cal_matriz:
                cols = st.columns(7)
                for i, dia in enumerate(semana):
                    if dia == 0:
                        cols[i].write("") # Espaço vazio no calendário
                    else:
                        # Cria uma caixinha para o dia. Se marcada, adiciona na lista de gravação.
                        if cols[i].checkbox(str(dia), key=f"chk_lote_{dia}"):
                            dias_marcados.append(f"{dia:02d}/{mes_num:02d}/{ano_sel}")
                            
            st.markdown("<br>", unsafe_allow_html=True)
            btn_lancar_lote = st.form_submit_button(f"🚀 Gravar Lançamentos Selecionados", type="primary", use_container_width=True)
            
            if btn_lancar_lote:
                if not dias_marcados:
                    st.warning("Selecione pelo menos um dia no calendário acima.")
                else:
                    for d_str in dias_marcados:
                        # Grava 1 dia isolado para cada caixinha marcada
                        cursor.execute("INSERT INTO lancamentos (colaborador_id, tipo, data_inicio, data_fim, numero_dias, valor_descontado) VALUES (%s, %s, %s, %s, %s, %s)",
                                       (colab_id, tipo_bd, d_str, d_str, 1, horas_abater))
                        if tipo_bd == "Folga BH":
                            cursor.execute("UPDATE colaboradores SET saldo_bh = saldo_bh - %s WHERE id = %s", (horas_abater, colab_id))
                            
                    st.success(f"{len(dias_marcados)} dia(s) de {tipo_bd} gravado(s) com sucesso!")
                    st.rerun()
                    
    # ----------------------------------------------------
    # HISTÓRICO DO COLABORADOR (Sempre visível)
    # ----------------------------------------------------
    st.markdown("---")
    st.subheader("Histórico de Lançamentos")
    cursor.execute("SELECT id, tipo, data_inicio, data_fim FROM lancamentos WHERE colaborador_id=%s ORDER BY id DESC", (colab_id,))
    historico = cursor.fetchall()
    
    for h_id, t, di, df in historico:
        c1, c2 = st.columns([4, 1])
        c1.write(f"**{t}**: {di} até {df}")
        if c2.button("🗑️ Excluir", key=f"del_{h_id}"):
            cursor.execute("SELECT numero_dias, tipo, valor_descontado FROM lancamentos WHERE id=%s", (h_id,))
            res = cursor.fetchone()
            if res:
                qd, tp, vdesc = res
                if tp == "Férias (Oficial)": cursor.execute("UPDATE colaboradores SET dias_pendentes = dias_pendentes - %s WHERE id=%s", (qd, colab_id))
                elif tp == "Férias (Efetivas)": cursor.execute("UPDATE colaboradores SET dias_pendentes = dias_pendentes + %s WHERE id=%s", (qd, colab_id))
                elif tp == "Folga BH": cursor.execute("UPDATE colaboradores SET saldo_bh = saldo_bh + %s WHERE id=%s", (float(vdesc)*qd, colab_id))
                cursor.execute("DELETE FROM lancamentos WHERE id=%s", (h_id,))
                st.rerun()

# ==========================================
# MÓDULO 4: FERIADOS
# ==========================================
elif menu == "🌴 Gerir Feriados":
    st.header("Gestão de Feriados")
    col1, col2 = st.columns(2)
    
    with col1:
        with st.form("form_feriado"):
            st.subheader("Novo Feriado")
            data_f = st.date_input("Data do Feriado", format="DD/MM/YYYY")
            desc_f = st.text_input("Descrição (Ex: Natal)")
            if st.form_submit_button("Salvar Feriado", use_container_width=True):
                try:
                    cursor.execute("INSERT INTO feriados (data_feriado, descricao) VALUES (%s, %s)", (data_f.strftime("%d/%m/%Y"), desc_f))
                    st.success("Feriado salvo!")
                    st.rerun()
                except:
                    st.error("Data já cadastrada.")
    
    with col2:
        st.subheader("Feriados Cadastrados")
        cursor.execute("SELECT id, data_feriado, descricao FROM feriados")
        for fid, dt, desc in cursor.fetchall():
            cc1, cc2 = st.columns([3, 1])
            cc1.write(f"★ **{dt}** - {desc}")
            if cc2.button("🗑️", key=f"fdel_{fid}"):
                cursor.execute("DELETE FROM feriados WHERE id=%s", (fid,))
                st.rerun()
