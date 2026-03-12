import pandas as pd
from datetime import datetime
import win32com.client as win32
import os

# CAMINHO DA PLANILHA NA JNL - Caminho confirmado para o seu OneDrive
CAMINHO_PLANILHA = r"C:\Users\Arthur\OneDrive - JNL COMÉRCIO EXTERIOR LTDA\Departamento Administrativo - Planilhas_Administrativo\PLANILHAS\CONTAS A RECEBER - PIX (ONLINE).xlsm"

def enviar_relatorio_financeiro():
    print("--- INICIANDO PROCESSO DA JNL ---")
    try:
        # 1. VERIFICAÇÃO DE SEGURANÇA
        if not os.path.exists(CAMINHO_PLANILHA):
            print(f"ERRO CRÍTICO: Planilha não encontrada em:\n{CAMINHO_PLANILHA}")
            return

        print("1. Planilha localizada com sucesso.")

        # 2. LEITURA DOS DADOS
        df = pd.read_excel(CAMINHO_PLANILHA, sheet_name='CONTAS EM ABERTO - PIX', header=2, engine='openpyxl')
        
        # Limpeza e conversão de dados
        df['DATA DE PAGAMENTO'] = pd.to_datetime(df['DATA DE PAGAMENTO'], errors='coerce')
        df['VALOR'] = pd.to_numeric(df['VALOR'], errors='coerce').fillna(0)
        df = df.dropna(subset=['EMPRESA', 'DATA DE PAGAMENTO'])
        
        hoje = datetime.now()
        vencidos = df[df['DATA DE PAGAMENTO'] < hoje]
        a_vencer = df[df['DATA DE PAGAMENTO'] >= hoje]

        # 3. LÓGICA PARA ITENS VENCIDOS
        if vencidos.empty:
            texto_vencidos = "Sem títulos pendentes"
        else:
            linhas = [f"{l['EMPRESA']}, {l['ORÇAMENTO']}, {l['PARCELA']}, R$ {l['VALOR']:,.2f}, {l['DATA DE PAGAMENTO'].strftime('%d/%m/%Y')}" for _, l in vencidos.iterrows()]
            # Une as linhas e adiciona o subtotal com espaço duplo antes
            texto_vencidos = "<br>".join(linhas) + f"<br><br>Subtotal: R$ {vencidos['VALOR'].sum():,.2f};"

        # 4. CÁLCULOS DE RESUMO
        total_a_vencer = a_vencer['VALOR'].sum()
        total_geral = df['VALOR'].sum()
        msg_proximo = df.sort_values(by='DATA DE PAGAMENTO').iloc[0]['EMPRESA'] if not a_vencer.empty else "Não há vencimentos próximos"

        # 5. MONTAGEM DO CORPO DO E-MAIL (Calibri 11)
        corpo = f"""<div style="font-family: 'Calibri', sans-serif; font-size: 11pt; color: black; line-height: 1.2;">Prezado(a), segue o resumo das contas a receber (PIX):<br><br>Itens já vencidos:<br><br>{texto_vencidos}<br><br>Itens a vencer: {len(a_vencer)} (Subtotal: R$ {total_a_vencer:,.2f});<br><br>Valor total em aberto: R$ {total_geral:,.2f};<br><br>Próximo vencimento: {msg_proximo}</div>"""

        # 6. CONEXÃO COM OUTLOOK E ASSINATURA DIGITAL
        outlook = win32.Dispatch('outlook.application')
        email = outlook.CreateItem(0)
        email.To = 'jessica@jnl.com.br'
        email.Subject = f"RELAÇÃO DE VENCIMENTOS - CONTAS A RECEBER (PIX) - {hoje.strftime('%d/%m/%Y')}"
        
        # Abre o e-mail para capturar a assinatura eletrónica configurada
        email.Display() 
        assinatura_outlook = email.HTMLBody
        
        # Une o relatório à assinatura sem espaços extras no final
        email.HTMLBody = corpo + assinatura_outlook
        
        email.Send()
        print("--- SUCESSO: E-mail enviado ---")

    except Exception as e:
        print(f"--- ERRO DURANTE A EXECUÇÃO: {e} ---")

if __name__ == "__main__":
    enviar_relatorio_financeiro()
