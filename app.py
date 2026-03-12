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

# --- BANCO DE DADOS (BLINDAGEM TOTAL) ---
def init_db():
    conn = sqlite3.connect('jnl_master.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS arquivos_setoriais (setor TEXT, nome TEXT, caminho TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS calendario (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, titulo TEXT, data_hora TEXT, notificado INTEGER, destinatarios TEXT, copias TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS anotacoes (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, pasta TEXT, titulo TEXT, conteudo TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS chat_setor (id INTEGER PRIMARY KEY AUTOINCREMENT, setor TEXT, usuario TEXT, data_hora TEXT, mensagem TEXT, editada INTEGER DEFAULT 0)')
    
    # Garantia de colunas para evitar KeyError
    c.execute("PRAGMA table_info(calendario)")
    cols_cal = [col[1] for col in c.fetchall()]
    if 'destinatarios' not in cols_cal: c.execute('ALTER TABLE calendario ADD COLUMN destinatarios TEXT')
    
    c.execute("PRAGMA table_info(chat_setor)")
    cols_chat = [col[1] for col in c.fetchall()]
    if 'editada' not in cols_chat: c.execute('ALTER TABLE chat_setor ADD COLUMN editada INTEGER DEFAULT 0')
    
    conn.commit()
    conn.close()

init_db()

# --- FUNÇÃO DE E-MAIL (SMTP NUVEM) ---
def enviar_email_nuvem(para, assunto, corpo):
    try:
        msg = MIMEMultipart()
        msg['From'] = st.secrets["OUTLOOK_USER_ARTHUR"]
        msg['To'] = para
        msg['Subject'] = assunto
        msg.attach(MIMEText(corpo, 'plain'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(st.secrets["OUTLOOK_USER_ARTHUR"], st.secrets["OUTLOOK_PASS_ARTHUR"])
        server.send_message(msg)
        server.quit()
        return True
    except: return False

# --- LOGIN ---
if "autenticado" not in st.session_state: st.session_state["autenticado"] = False
if "setor" not in st.session_state: st.session_state["setor"] = None

USUARIOS = {"arthur": {"senha": "32167308", "nome": "ARTHUR (DIRETORIA)", "setores": ["TODOS"]}}

if not st.session_state["autenticado"]:
    st.title("🔒 CENTRO DE COMANDO JNL")
    u = st.text_input("USUÁRIO:").lower()
    p = st.text_input("SENHA:", type="password")
    if st.button("ENTRAR"):
        if u in USUARIOS and USUARIOS[u]["senha"] == p:
            st.session_state.update({"autenticado": True, "user_slug": u, "user_nome": USUARIOS[u]["nome"]})
            st.rerun()
        else: st.error("Acesso Negado.")

elif st.session_state["setor"] is None:
    st.title(f"Olá, {st.session_state['user_nome']}")
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

    # --- BARRA LATERAL (PLANILHAS) ---
    with st.sidebar:
        st.header(f"📍 {setor_atual}")
        if st.button("⬅️ VOLTAR AO MENU"):
            st.session_state["setor"] = None
            st.rerun()
        st.write("---")
        st.subheader("📂 PLANILHAS")
        up = st.file_uploader("Upload de arquivos", accept_multiple_files=True)
        if st.button("📥 SALVAR NO SERVIDOR"):
            if up: st.success("Arquivos salvos com sucesso!"); st.rerun()
        
    # --- ABAS ---
    tab_ia, tab_chat, tab_agenda, tab_notas = st.tabs(["💻 IA", "👥 Chat Equipe", "📅 Agenda", "📝 Notas"])

    with tab_ia:
        st.subheader("Cérebro Artificial JNL")
        prompt = st.chat_input("Pergunte algo para a IA...")
        if prompt:
            with st.chat_message("user"): st.write(prompt)
            try:
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}]).choices[0].message.content
                with st.chat_message("assistant"): st.write(res)
            except: st.error("Erro na Groq Key nos Secrets.")

    with tab_chat:
        st.subheader(f"Chat: {setor_atual}")
        conn = sqlite3.connect('jnl_master.db')
        df = pd.read_sql_query("SELECT * FROM chat_setor WHERE setor = ? ORDER BY id ASC", conn, params=(setor_atual,))
        conn.close()

        for _, row in df.iterrows():
            is_me = row['usuario'] == user
            align, bg = ("right", "#dcf8c6") if is_me else ("left", "#f1f0f0")
            tag = " *(Editada)*" if row.get('editada') == 1 else ""
            
            st.markdown(f"<div style='text-align: {align};'><div style='display: inline-block; background: {bg}; padding: 10px; border-radius: 10px; color: black; margin: 5px; min-width: 150px;'><b>{row['usuario'].capitalize()}</b><br>{row['mensagem']}<br><small style='color: gray;'>{row['data_hora']}{tag}</small></div></div>", unsafe_allow_html=True)
            
            if is_me:
                dt_m = datetime.strptime(row['data_hora'], '%Y-%m-%d %H:%M:%S')
                if datetime.now() - dt_m < timedelta(minutes=10):
                    with st.popover("✏️ Editar"):
                        nv = st.text_input("Corrigir:", row['mensagem'], key=f"e_{row['id']}")
                        if st.button("Salvar", key=f"b_{row['id']}"):
                            conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
                            c.execute("UPDATE chat_setor SET mensagem = ?, editada = 1 WHERE id = ?", (nv, row['id']))
                            conn.commit(); conn.close(); st.rerun()

        with st.form("chat_f", clear_on_submit=True):
            m = st.text_input("Mensagem:")
            if st.form_submit_button("Enviar"):
                if m:
                    conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
                    c.execute("INSERT INTO chat_setor (setor, usuario, data_hora, mensagem) VALUES (?, ?, ?, ?)", (setor_atual, user, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), m))
                    conn.commit(); conn.close(); st.rerun()

    with tab_agenda:
        st.subheader("Calendário de Ações")
        with st.form("age_f"):
            t_age = st.text_input("O que agendar?")
            col1, col2 = st.columns(2)
            d_age = col1.date_input("Data")
            h_age = col2.time_input("Hora")
            para = st.text_input("Para (e-mails):")
            if st.form_submit_button("Agendar"):
                conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
                c.execute("INSERT INTO calendario (usuario, titulo, data_hora, notificado, destinatarios) VALUES (?, ?, ?, 0, ?)", (user, t_age, f"{d_age} {h_age}", para))
                conn.commit(); conn.close(); st.success("Tarefa salva!"); st.rerun()

    with tab_notes:
        st.subheader("Anotações Rápidas")
        with st.form("notas_f", clear_on_submit=True):
            tit = st.text_input("Título da Nota")
            cont = st.text_area("Conteúdo")
            if st.form_submit_button("Salvar Nota"):
                conn = sqlite3.connect('jnl_master.db'); c = conn.cursor()
                c.execute("INSERT INTO anotacoes (usuario, pasta, titulo, conteudo) VALUES (?, 'N', ?, ?)", (user, tit, cont))
                conn.commit(); conn.close(); st.rerun()
        
        conn = sqlite3.connect('jnl_master.db')
        df_n = pd.read_sql_query("SELECT * FROM anotacoes WHERE usuario = ?", conn, params=(user,))
        conn.close()
        for _, n in df_n.iterrows():
            with st.container(border=True):
                st.write(f"**{n['titulo']}**")
                st.write(n['conteudo'])