import streamlit as st
import pandas as pd
import sqlite3
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from groq import Groq

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SISTEMA JNL", page_icon="🏢", layout="wide")

# --- BANCO DE DADOS (COM CORREÇÃO DE COLUNAS) ---
def init_db():
    conn = sqlite3.connect('jnl_master.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS arquivos_setoriais (setor TEXT, nome TEXT, caminho TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS calendario (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, titulo TEXT, data_hora TEXT, notificado INTEGER, destinatarios TEXT, copias TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS anotacoes (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, pasta TEXT, titulo TEXT, conteudo TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS chat_setor (id INTEGER PRIMARY KEY AUTOINCREMENT, setor TEXT, usuario TEXT, data_hora TEXT, mensagem TEXT, editada INTEGER DEFAULT 0)')
    
    c.execute("PRAGMA table_info(calendario)")
    colunas = [col[1] for col in c.fetchall()]
    if 'destinatarios' not in colunas: c.execute('ALTER TABLE calendario ADD COLUMN destinatarios TEXT')
    if 'copias' not in colunas: c.execute('ALTER TABLE calendario ADD COLUMN copias TEXT')
    
    conn.commit()
    conn.close()

init_db()

# --- ESTADO DA SESSÃO ---
if "autenticado" not in st.session_state: st.session_state["autenticado"] = False
if "setor" not in st.session_state: st.session_state["setor"] = None

USUARIOS = {
    "arthur": {"senha": "32167308", "nome": "ARTHUR (DIRETORIA)", "setores": ["TODOS"], "email": "arthur@jnl.com.br"},
    "joãozinho": {"senha": "123", "nome": "JOÃOZINHO", "setores": ["ADMINISTRATIVO"], "email": "joaozinho@jnl.com.br"}
}

# --- LOGIN ---
if not st.session_state["autenticado"]:
    st.title("🔒 ACESSO RESTRITO - JNL")
    u = st.text_input("USUÁRIO:").lower()
    p = st.text_input("SENHA:", type="password")
    if st.button("ENTRAR"):
        if u in USUARIOS and USUARIOS[u]["senha"] == p:
            st.session_state.update({"autenticado": True, "user_slug": u, "user_nome": USUARIOS[u]["nome"], "permissoes": USUARIOS[u]["setores"]})
            st.rerun()
        else: st.error("Acesso Negado.")

elif st.session_state["setor"] is None:
    st.title(f"Olá, {st.session_state['user_nome']}")
    setores_lista = ["ADMINISTRATIVO", "FINANCEIRO", "VENDAS", "COMPRAS", "SOLUÇÕES CORPORATIVAS", "GERAL"]
    cols = st.columns(3)
    for i, s in enumerate(setores_lista):
        with cols[i % 3]:
            if st.button(s, use_container_width=True):
                st.session_state["setor"] = s
                st.rerun()
else:
    setor_atual = st.session_state["setor"]
    usuario_logado = st.session_state["user_slug"]
    
    with st.sidebar:
        st.header(f"📍 {setor_atual}")
        if st.button("⬅️ VOLTAR AO MENU"): st.session_state["setor"] = None; st.rerun()
        st.write("---")
        up = st.file_uploader("Upload Planilhas", accept_multiple_files=True)
        if st.button("📥 SALVAR"):
            if up: st.success("Salvo localmente!"); st.rerun()

    tab_ia, tab_chat, tab_agenda, tab_notas = st.tabs(["💬 IA", "👥 Equipe", "📅 Agenda", "📝 Notas"])

    with tab_ia:
        prompt = st.chat_input("Fale com a IA JNL...")
        if prompt:
            with st.chat_message("user"): st.write(prompt)
            try:
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}]).choices[0].message.content
                with st.chat_message("assistant"): st.write(res)
            except: st.error("Erro na Groq Key.")

    with tab_chat:
        conn = sqlite3.connect('jnl_master.db')
        df_msgs = pd.read_sql_query("SELECT * FROM chat_setor WHERE setor = ? ORDER BY id ASC", conn, params=(setor_atual,))
        for _, row in df_msgs.iterrows():
            is_me = row['usuario'] == usuario_logado
            align, bg = ("right", "#dcf8c6") if is_me else ("left", "#f1f0f0")
            tag = " *(Editada)*" if row.get('editada') == 1 else ""
            st.markdown(f"<div style='text-align: {align};'><div style='display: inline-block; background: {bg}; padding: 10px; border-radius: 10px; color: black; margin: 5px;'><b>{row['usuario'].capitalize()}</b><br>{row['mensagem']}<br><small>{row['data_hora']}{tag}</small></div></div>", unsafe_allow_html=True)
            if is_me:
                # Edição permitida apenas em 10 minutos
                dt_msg = datetime.strptime(row['data_hora'], '%d/%m/%Y %H:%M') if '/' in row['data_hora'] else datetime.now()
                if datetime.now() - dt_msg < timedelta(minutes=10):
                    with st.popover("✏️"):
                        nv = st.text_input("Corrigir:", row['mensagem'], key=f"c_{row['id']}")
                        if st.button("Confirmar", key=f"b_{row['id']}"):
                            c = conn.cursor(); c.execute("UPDATE chat_setor SET mensagem = ?, editada = 1 WHERE id = ?", (nv, row['id'])); conn.commit(); st.rerun()
        conn.close()
        with st.form("f_chat", clear_on_submit=True):
            m = st.text_input("Mensagem:")
            if st.form_submit_button("Enviar"):
                if m:
                    conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
                    agora = (datetime.utcnow() - timedelta(hours=3)).strftime('%d/%m/%Y %H:%M')
                    c.execute("INSERT INTO chat_setor (setor, usuario, data_hora, mensagem) VALUES (?, ?, ?, ?)", (setor_atual, usuario_logado, agora, m))
                    conn.commit(); conn.close(); st.rerun()

    with tab_agenda:
        with st.form("f_cal"):
            t = st.text_input("Tarefa:", placeholder="Ex: Conferir estoque")
            col1, col2 = st.columns(2)
            d = col1.date_input("Data")
            h = col2.time_input("Hora")
            p = st.text_input("Para (e-mail):", placeholder="financeiro@jnl.com.br")
            cc = st.text_input("Cc (Cópia):", placeholder="diretoria@jnl.com.br")
            if st.form_submit_button("AGENDAR"):
                conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
                c.execute("INSERT INTO calendario (usuario, titulo, data_hora, notificado, destinatarios, copias) VALUES (?, ?, ?, 0, ?, ?)", (usuario_logado, t, f"{d} {h}", p, cc))
                conn.commit(); conn.close(); st.success("Agendado!"); st.rerun()

    with tab_notas:
        with st.form("f_nota", clear_on_submit=True):
            t_n = st.text_input("Título")
            c_n = st.text_area("Conteúdo")
            if st.form_submit_button("Salvar Nota"):
                conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
                c.execute("INSERT INTO anotacoes (usuario, pasta, titulo, conteudo) VALUES (?, 'N', ?, ?)", (usuario_logado, t_n, c_n))
                conn.commit(); conn.close(); st.rerun()
        
        conn = sqlite3.connect('jnl_master.db')
        df_n = pd.read_sql_query("SELECT * FROM anotacoes WHERE usuario = ?", conn, params=(usuario_logado,))
        for _, row in df_n.iterrows():
            with st.container(border=True):
                st.write(f"**{row['titulo']}**")
                st.write(row['conteudo'])
                col_n1, col_n2 = st.columns(2)
                with col_n1.popover("✏️ Editar"):
                    nt = st.text_input("Título", row['titulo'], key=f"tn_{row['id']}")
                    nc = st.text_area("Conteúdo", row['conteudo'], key=f"cn_{row['id']}")
                    if st.button("Salvar", key=f"sn_{row['id']}"):
                        c = conn.cursor(); c.execute("UPDATE anotacoes SET titulo = ?, conteudo = ? WHERE id = ?", (nt, nc, row['id'])); conn.commit(); st.rerun()
                if col_n2.button("🗑️ Apagar", key=f"dn_{row['id']}"):
                    c = conn.cursor(); c.execute("DELETE FROM anotacoes WHERE id = ?", (row['id'],)); conn.commit(); st.rerun()
        conn.close()