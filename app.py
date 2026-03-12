import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime, timedelta
from groq import Groq

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="SISTEMA JNL", page_icon="🏢", layout="wide")

# --- BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('jnl_master.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS calendario (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, titulo TEXT, data_hora TEXT, notificado INTEGER, destinatarios TEXT, copias TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS anotacoes (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, titulo TEXT, conteudo TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS chat_setor (id INTEGER PRIMARY KEY AUTOINCREMENT, setor TEXT, usuario TEXT, data_hora TEXT, mensagem TEXT, editada INTEGER DEFAULT 0)')
    c.execute('CREATE TABLE IF NOT EXISTS perfil_usuario (usuario TEXT PRIMARY KEY, nome_tratamento TEXT, instrucoes_ia TEXT)')
    conn.commit()
    conn.close()

init_db()

# --- SAUDAÇÃO INTELIGENTE ---
def saudacao():
    hora = datetime.now().hour
    if 5 <= hora < 12: return "Bom dia"
    elif 12 <= hora < 18: return "Boa tarde"
    else: return "Boa noite"

# --- LOGIN E SESSÃO ---
if "autenticado" not in st.session_state: st.session_state["autenticado"] = False
if "setor" not in st.session_state: st.session_state["setor"] = None
if "mensagens_ia" not in st.session_state: st.session_state["mensagens_ia"] = []

USUARIOS = {"arthur": {"senha": "32167308", "nome": "ARTHUR"}}

if not st.session_state["autenticado"]:
    st.title("🔒 CENTRO DE COMANDO JNL")
    u = st.text_input("Usuário:").lower()
    p = st.text_input("Senha:", type="password")
    if st.button("ACESSAR"):
        if u in USUARIOS and USUARIOS[u]["senha"] == p:
            st.session_state.update({"autenticado": True, "user_slug": u})
            st.rerun()
        else: st.error("Erro!")

elif st.session_state["setor"] is None:
    st.title(f"🏢 {saudacao()}! Bem-vindo à JNL Importadora.")
    setores = ["ADMINISTRATIVO", "FINANCEIRO", "VENDAS", "COMPRAS", "SOLUÇÕES CORPORATIVAS", "GERAL"]
    cols = st.columns(3)
    for i, s in enumerate(setores):
        with cols[i % 3]:
            if st.button(s, use_container_width=True):
                st.session_state["setor"] = s
                st.rerun()
else:
    setor_atual = st.session_state["setor"]
    user = st.session_state["user_slug"]

    # RECUPERAR MEMÓRIA
    conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
    c.execute("SELECT nome_tratamento, instrucoes_ia FROM perfil_usuario WHERE usuario = ?", (user,))
    perfil = c.fetchone()
    nome_ia = perfil[0] if perfil else "Comandante"
    inst_ia = perfil[1] if perfil else ""
    conn.close()

    with st.sidebar:
        st.header(f"📍 {setor_atual}")
        if st.button("⬅️ VOLTAR"): st.session_state["setor"] = None; st.rerun()
        st.write("---")
        with st.expander("⚙️ MEU PERFIL (MEMÓRIA IA)"):
            n_nome = st.text_input("Como a IA deve te chamar?", value=nome_ia)
            n_inst = st.text_area("Instruções Fixas:", value=inst_ia, placeholder="Ex: Sempre use o modelo de orçamento X...")
            if st.button("Salvar Perfil"):
                conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
                c.execute("INSERT OR REPLACE INTO perfil_usuario (usuario, nome_tratamento, instrucoes_ia) VALUES (?, ?, ?)", (user, n_nome, n_inst))
                conn.commit(); conn.close(); st.rerun()

    tab_ia, tab_chat, tab_agenda, tab_notes = st.tabs(["💬 IA JNL", "👥 EQUIPE", "📅 AGENDA", "📝 NOTAS"])

    with tab_ia:
        st.subheader(f"Assistente JNL - {saudacao()}, {nome_ia}")
        for msg in st.session_state["mensagens_ia"]:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
        
        if prompt := st.chat_input("Fale com o sistema..."):
            st.session_state["mensagens_ia"].append({"role": "user", "content": prompt})
            with st.chat_message("user"): st.markdown(prompt)
            with st.chat_message("assistant"):
                try:
                    ctx = f"Você é o assistente da JNL. O usuário é {nome_ia}. Regras: {inst_ia}"
                    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                    resp = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "system", "content": ctx}] + st.session_state["mensagens_ia"]).choices[0].message.content
                    st.markdown(resp); st.session_state["mensagens_ia"].append({"role": "assistant", "content": resp})
                except: st.error("Verifique a chave Groq.")

    with tab_chat:
        st.subheader("Chat do Setor")
        conn = sqlite3.connect('jnl_master.db')
        df_c = pd.read_sql_query("SELECT * FROM chat_setor WHERE setor = ? ORDER BY id ASC", conn, params=(setor_atual,))
        for _, row in df_c.iterrows():
            is_me = row['usuario'] == user
            align, bg = ("right", "#dcf8c6") if is_me else ("left", "#f1f0f0")
            st.markdown(f"<div style='text-align: {align};'><div style='display: inline-block; background: {bg}; padding: 10px; border-radius: 10px; color: black; margin: 5px; min-width: 200px;'><b>{row['usuario'].upper()}</b><br>{row['mensagem']}</div></div>", unsafe_allow_html=True)
            if is_me:
                with st.popover("✏️"):
                    nv = st.text_input("Editar:", row['mensagem'], key=f"ec_{row['id']}")
                    if st.button("Salvar", key=f"bc_{row['id']}"):
                        c = conn.cursor(); c.execute("UPDATE chat_setor SET mensagem = ?, editada = 1 WHERE id = ?", (nv, row['id'])); conn.commit(); st.rerun()
        
        with st.form("chat_f", clear_on_submit=True):
            m = st.text_input("Mensagem:")
            if st.form_submit_button("Enviar"):
                if m:
                    c = conn.cursor(); agora = (datetime.now()).strftime('%d/%m %H:%M')
                    c.execute("INSERT INTO chat_setor (setor, usuario, data_hora, mensagem) VALUES (?, ?, ?, ?)", (setor_atual, user, agora, m))
                    conn.commit(); st.rerun()
        conn.close()

    with tab_agenda:
        st.subheader("Agenda de Ações")
        with st.form("age_f"):
            t_age = st.text_input("Título da Tarefa")
            c1, c2 = st.columns(2)
            d_age = c1.date_input("Data")
            h_age = c2.time_input("Hora")
            p_age = st.text_input("Para")
            cc_age = st.text_input("Cc")
            if st.form_submit_button("AGENDAR"):
                conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
                c.execute("INSERT INTO calendario (usuario, titulo, data_hora, notificado, destinatarios, copias) VALUES (?, ?, ?, 0, ?, ?)", (user, t_age, f"{d_age} {h_age}", p_age, cc_age))
                conn.commit(); conn.close(); st.success("Agendado!"); st.rerun()

        st.write("---")
        conn = sqlite3.connect('jnl_master.db')
        df_res = pd.read_sql_query("SELECT * FROM calendario WHERE usuario = ?", conn, params=(user,))
        for _, r in df_res.iterrows():
            vencido = datetime.strptime(r['data_hora'], '%Y-%m-%d %H:%M:%S') < datetime.now()
            status = "🔴 VENCIDO" if vencido else "🟢 NO PRAZO"
            with st.container(border=True):
                col1, col2 = st.columns([4, 1])
                col1.write(f"**{r['titulo']}** | {status}")
                col1.write(f"📅 {r['data_hora']} | ✉️ {r['destinatarios']}")
                if col2.button("🗑️", key=f"da_{r['id']}"):
                    c = conn.cursor(); c.execute("DELETE FROM calendario WHERE id = ?", (r['id'],)); conn.commit(); st.rerun()
        conn.close()

    with tab_notes:
        st.subheader("Bloco de Notas")
        with st.form("nota_form", clear_on_submit=True):
            tn = st.text_input("Título")
            cn = st.text_area("Conteúdo")
            if st.form_submit_button("Salvar Nota"):
                conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
                c.execute("INSERT INTO anotacoes (usuario, titulo, conteudo) VALUES (?, ?, ?)", (user, tn, cn))
                conn.commit(); conn.close(); st.rerun()
        
        conn = sqlite3.connect('jnl_master.db')
        df_n = pd.read_sql_query("SELECT * FROM anotacoes WHERE usuario = ?", conn, params=(user,))
        for _, n in df_n.iterrows():
            with st.container(border=True):
                st.write(f"**{n['titulo']}**")
                st.write(n['conteudo'])
                c1, c2 = st.columns(2)
                with c1.popover("✏️ Editar"):
                    ut = st.text_input("Novo Título", n['titulo'], key=f"un_{n['id']}")
                    uc = st.text_area("Novo Conteúdo", n['conteudo'], key=f"uc_{n['id']}")
                    if st.button("Confirmar", key=f"usb_{n['id']}"):
                        c = conn.cursor(); c.execute("UPDATE anotacoes SET titulo = ?, conteudo = ? WHERE id = ?", (ut, uc, n['id'])); conn.commit(); st.rerun()
                if c2.button("🗑️", key=f"udn_{n['id']}"):
                    c = conn.cursor(); c.execute("DELETE FROM anotacoes WHERE id = ?", (n['id'],)); conn.commit(); st.rerun()
        conn.close()