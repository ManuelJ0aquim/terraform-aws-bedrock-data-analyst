import json
import logging
import os
import re
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
s3 = boto3.client("s3")
# Cliente correto para gerir as sessões e sandboxes do Code Interpreter em tempo de execução
agent_runtime = boto3.client("bedrock-agent-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))

# Environment variables
RAW_BUCKET = os.environ["RAW_BUCKET"]
RESULTS_BUCKET = os.environ["RESULTS_BUCKET"]
CODE_INTERPRETER_ID = os.environ["CODE_INTERPRETER_ID"]

def generate_python_code(query):
    """
    Invoca o Amazon Nova 2 Lite usando o perfil de inferência cross-region
    para otimizar a distribuição de carga e contornar limites de quotas regionais.
    """
    # Identificador do Inference Profile Cross-Region (US) para o Nova 2 Lite
    MODEL_ID = "us.amazon.nova-2-lite-v1:0"

    # Cliente Bedrock Runtime em us-east-1 (capaz de resolver perfis "us.")
    bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-east-1')

    prompt = f"""És um Engenheiro e Analista de Dados especialista em Python e Pandas.
O teu objetivo é escrever um script Python completo para responder à seguinte pergunta do utilizador sobre um ficheiro de transações bancárias.

Pergunta do Utilizador: "{query}"

Informações do Ambiente e Dataset:
- O ficheiro está no S3 no bucket "{RAW_BUCKET}" com a key "sample_sales.csv".
- As colunas do CSV são: transaction_id, customer_id, date, account_type, transaction_type, amount, balance_after, merchant_category, risk_score, is_fraud, channel, location
- Regras de Mapeamento de Negócio:
  1. "Volume financeiro", "faturamento" ou "gastos totais" refere-se à soma da coluna 'amount'.
  2. "Fraude" ativa quando a coluna 'is_fraud' é igual a 1.
  3. "Saldo negativo" ou "contas a descoberto" ocorre quando 'balance_after' < 0.

Instruções para o código Python:
1. Usa boto3 para descarregar o ficheiro de s3://{RAW_BUCKET}/sample_sales.csv para '/tmp/sample_sales.csv'.
2. Carrega o CSV usando pandas.
3. Faz a análise exata para responder à pergunta.
4. Imprime claramente o resultado final formatado no console (stdout).

REGRAS ESTRITAS:
- Retorna APENAS o código Python executável.
- Não inclua explicações, comentários fora do código ou tags de formatação markdown adicionais além do código.
"""

    # Estrutura padrão de mensagens (Messages API) suportada pela família Amazon Nova
    body = json.dumps({
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "inferenceConfig": {
            "maxNewTokens": 1000,
            "temperature": 0.1
        }
    })

    logger.info("Solicitando ao Bedrock LLM (Amazon Nova 2 Lite Cross-Region)...")
    
    response = bedrock_runtime.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=body
    )

    response_body = json.loads(response["body"].read())
    
    # Extração de texto adaptada à estrutura de output da API do Amazon Nova
    generated_text = ""
    if "output" in response_body and "message" in response_body["output"]:
        content_list = response_body["output"]["message"].get("content", [])
        if content_list and "text" in content_list[0]:
            generated_text = content_list[0]["text"]

    # Limpeza de formatações markdown do código
    cleaned_code = re.sub(r"^```python\n", "", generated_text, flags=re.MULTILINE)
    cleaned_code = re.sub(r"^```\n?", "", cleaned_code, flags=re.MULTILINE).strip()

    logger.info("Código Python gerado pela IA:\n%s", cleaned_code)
    return cleaned_code


def start_session():
    """Inicia sessão no Bedrock Agent Runtime Code Interpreter."""
    response = agent_runtime.start_session(
        sessionIdentifier=CODE_INTERPRETER_ID,
    )
    session_id = response["sessionId"]
    logger.info("Code Interpreter session started: %s", session_id)
    return session_id


def execute_code(session_id, code):
    """Executa o código Python dentro da sandbox do Code Interpreter."""
    response = agent_runtime.optimize_and_execute_code(
        sessionIdentifier=CODE_INTERPRETER_ID,
        sessionId=session_id,
        codeBlock={
            "language": "python",
            "code": code
        }
    )
    return response.get("output", "")


def stop_session(session_id):
    """Encerra a sessão do Code Interpreter."""
    agent_runtime.end_session(
        sessionIdentifier=CODE_INTERPRETER_ID,
        sessionId=session_id,
    )
    logger.info("Code Interpreter session stopped: %s", session_id)


def save_result(query, code_used, result):
    """Guarda o resultado da análise no S3."""
    key = "analysis-result.json"
    body = json.dumps(
        {
            "query": query,
            "generated_code": code_used,
            "result": result,
        },
        indent=2,
        ensure_ascii=False,
    )

    s3.put_object(
        Bucket=RESULTS_BUCKET,
        Key=key,
        Body=body.encode("utf-8"),
        ContentType="application/json",
    )

    logger.info("Analysis result saved to s3://%s/%s", RESULTS_BUCKET, key)
    return key


def lambda_handler(event, context):
    logger.info("Received event: %s", json.dumps(event))

    # Pergunta padrão adaptada ao novo contexto bancário
    query = event.get(
        "query",
        "Qual é o canal digital que regista o maior volume financeiro em transações fraudulentas?",
    )

    logger.info("User query: %s", query)
    session_id = None

    try:
        # 1. IA gera o código dinamicamente para a pergunta específica
        python_code = generate_python_code(query)

        # 2. Inicia a sandbox do Code Interpreter
        session_id = start_session()

        # 3. Executa o código gerado na sandbox
        logger.info("Executing generated code in Code Interpreter sandbox...")
        execution_result = execute_code(session_id, python_code)

        logger.info("Execution result: %s", execution_result)

        # 4. Guarda os resultados no S3
        result_key = save_result(query, python_code, execution_result)

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "query": query,
                    "generated_code": python_code,
                    "result": execution_result,
                    "result_s3": f"s3://{RESULTS_BUCKET}/{result_key}",
                },
                ensure_ascii=False,
            ),
        }

    except Exception as exc:
        logger.exception("Error executing data analysis")
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "error": str(exc),
                },
                ensure_ascii=False,
            ),
        }

    finally:
        if session_id:
            try:
                stop_session(session_id)
            except Exception:
                logger.exception("Failed to stop Code Interpreter session")
