import json
import logging
import os
import re
import time

import boto3
from botocore.exceptions import ClientError


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger()
logger.setLevel(logging.INFO)


# ============================================================
# AWS CLIENTS
# ============================================================

s3 = boto3.client("s3")

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

agent_runtime = boto3.client(
    "bedrock-agent-runtime",
    region_name=AWS_REGION,
)

bedrock_runtime = boto3.client(
    "bedrock-runtime",
    region_name="us-east-1",
)


# ============================================================
# ENVIRONMENT VARIABLES
# ============================================================

RAW_BUCKET = os.environ["RAW_BUCKET"]
RESULTS_BUCKET = os.environ["RESULTS_BUCKET"]
CODE_INTERPRETER_ID = os.environ["CODE_INTERPRETER_ID"]


# ============================================================
# CONFIGURATION
# ============================================================

MODEL_ID = "us.amazon.nova-2-lite-v1:0"

MAX_NEW_TOKENS = 600
TEMPERATURE = 0

MAX_RETRIES = 3

RETRY_BASE_DELAY = 2


# ============================================================
# GENERATE PYTHON CODE WITH AMAZON NOVA
# ============================================================

def generate_python_code(query):
    """
    Invoca o Amazon Nova 2 Lite para gerar código Python
    capaz de responder à pergunta do utilizador.
    """

    prompt = f"""
És um especialista em Python, Pandas e análise de dados bancários.

Gera APENAS código Python executável para responder à pergunta:

{query}

Dataset:
s3://{RAW_BUCKET}/sample_sales.csv

Colunas:
transaction_id, customer_id, date, account_type, transaction_type,
amount, balance_after, merchant_category, risk_score, is_fraud,
channel, location

Regras de negócio:
- volume financeiro, faturamento ou gastos totais = soma de amount
- fraude = is_fraud == 1
- saldo negativo = balance_after < 0

O código deve:

1. Usar boto3 para baixar:
   s3://{RAW_BUCKET}/sample_sales.csv

2. Guardar o ficheiro em:
   /tmp/sample_sales.csv

3. Carregar o CSV com pandas.

4. Fazer exatamente a análise necessária para responder à pergunta.

5. Imprimir claramente o resultado final.

IMPORTANTE:
- Retorna SOMENTE código Python.
- Não uses markdown.
- Não uses ```python.
- Não escrevas explicações.
- Não inventes dados.
"""

    body = json.dumps(
        {
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
                "maxNewTokens": MAX_NEW_TOKENS,
                "temperature": TEMPERATURE,
            },
        }
    )

    logger.info(
        "Invocando Amazon Nova 2 Lite. model=%s",
        MODEL_ID,
    )

    for attempt in range(MAX_RETRIES + 1):

        try:
            response = bedrock_runtime.invoke_model(
                modelId=MODEL_ID,
                contentType="application/json",
                accept="application/json",
                body=body,
            )

            response_body = json.loads(
                response["body"].read()
            )

            generated_text = extract_generated_text(
                response_body
            )

            cleaned_code = clean_generated_code(
                generated_text
            )

            validate_generated_code(cleaned_code)

            logger.info(
                "Código Python gerado com sucesso."
            )

            logger.info(
                "Código gerado:\n%s",
                cleaned_code,
            )

            return cleaned_code

        except ClientError as exc:

            error_code = exc.response.get(
                "Error",
                {}
            ).get(
                "Code",
                "Unknown"
            )

            error_message = exc.response.get(
                "Error",
                {}
            ).get(
                "Message",
                str(exc)
            )

            logger.error(
                "Bedrock ClientError: code=%s message=%s",
                error_code,
                error_message,
            )

            # ------------------------------------------------
            # Quota diária de tokens
            # ------------------------------------------------

            if "Too many tokens per day" in error_message:

                raise RuntimeError(
                    "A quota diária de tokens do "
                    "Amazon Nova 2 Lite foi atingida. "
                    "Aguarde a renovação da quota ou "
                    "aumente a quota do Amazon Bedrock "
                    "no AWS Service Quotas."
                ) from exc

            # ------------------------------------------------
            # Throttling temporário
            # ------------------------------------------------

            if error_code in (
                "ThrottlingException",
                "TooManyRequestsException",
            ):

                if attempt >= MAX_RETRIES:

                    raise RuntimeError(
                        "O Amazon Bedrock continua "
                        "limitando as requisições após "
                        f"{MAX_RETRIES} tentativas."
                    ) from exc

                delay = RETRY_BASE_DELAY * (
                    2 ** attempt
                )

                logger.warning(
                    "Throttling temporário. "
                    "Tentativa %s/%s. "
                    "Aguardando %s segundos.",
                    attempt + 1,
                    MAX_RETRIES,
                    delay,
                )

                time.sleep(delay)
                continue

            raise

        except Exception:
            logger.exception(
                "Erro inesperado ao invocar o Bedrock."
            )
            raise

    raise RuntimeError(
        "Não foi possível gerar o código Python."
    )


# ============================================================
# EXTRACT MODEL RESPONSE
# ============================================================

def extract_generated_text(response_body):
    """
    Extrai o texto da resposta do Amazon Nova.
    """

    try:
        content = (
            response_body
            ["output"]
            ["message"]
            ["content"]
        )

        if not content:
            raise ValueError(
                "A resposta do modelo não contém content."
            )

        for item in content:

            if isinstance(item, dict):

                text = item.get("text")

                if text:
                    return text

        raise ValueError(
            "Nenhum texto encontrado na resposta do modelo."
        )

    except (KeyError, TypeError) as exc:

        logger.error(
            "Resposta inesperada do Bedrock: %s",
            response_body,
        )

        raise RuntimeError(
            "O Bedrock retornou uma resposta "
            "em formato inesperado."
        ) from exc


# ============================================================
# CLEAN GENERATED CODE
# ============================================================

def clean_generated_code(text):
    """
    Remove markdown ou pequenos artefactos que o modelo
    eventualmente coloque em volta do código.
    """

    if not text:
        raise RuntimeError(
            "O modelo não retornou código."
        )

    code = text.strip()

    # Remove ```python
    code = re.sub(
        r"^\s*```python\s*",
        "",
        code,
        flags=re.IGNORECASE,
    )

    # Remove ```
    code = re.sub(
        r"^\s*```\s*",
        "",
        code,
    )

    code = re.sub(
        r"\s*```\s*$",
        "",
        code,
    )

    return code.strip()


# ============================================================
# VALIDATE GENERATED CODE
# ============================================================

def validate_generated_code(code):
    """
    Validação básica antes de enviar o código ao Code Interpreter.
    """

    if not code:
        raise RuntimeError(
            "O código Python gerado está vazio."
        )

    dangerous_patterns = [
        "subprocess",
        "os.system",
        "eval(",
        "exec(",
        "__import__",
    ]

    for pattern in dangerous_patterns:

        if pattern in code:

            raise RuntimeError(
                f"O código gerado contém uma operação "
                f"não permitida: {pattern}"
            )

    required_indicators = [
        "pandas",
        "boto3",
        "sample_sales.csv",
    ]

    for indicator in required_indicators:

        if indicator not in code:

            raise RuntimeError(
                "O código gerado não contém "
                f"o componente esperado: {indicator}"
            )


# ============================================================
# START CODE INTERPRETER SESSION
# ============================================================

def start_session():
    """
    Inicia uma sessão no Bedrock Code Interpreter.
    """

    logger.info(
        "Iniciando sessão do Code Interpreter."
    )

    response = agent_runtime.start_session(
        sessionIdentifier=CODE_INTERPRETER_ID,
    )

    session_id = response["sessionId"]

    logger.info(
        "Code Interpreter session started: %s",
        session_id,
    )

    return session_id


# ============================================================
# EXECUTE CODE
# ============================================================

def execute_code(session_id, code):
    """
    Executa o código Python dentro da sandbox.
    """

    logger.info(
        "Executando código no Code Interpreter."
    )

    response = agent_runtime.optimize_and_execute_code(
        sessionIdentifier=CODE_INTERPRETER_ID,
        sessionId=session_id,
        codeBlock={
            "language": "python",
            "code": code,
        },
    )

    output = response.get(
        "output",
        "",
    )

    return output


# ============================================================
# STOP CODE INTERPRETER SESSION
# ============================================================

def stop_session(session_id):
    """
    Encerra a sessão do Code Interpreter.
    """

    if not session_id:
        return

    logger.info(
        "Encerrando sessão do Code Interpreter: %s",
        session_id,
    )

    agent_runtime.end_session(
        sessionIdentifier=CODE_INTERPRETER_ID,
        sessionId=session_id,
    )

    logger.info(
        "Code Interpreter session stopped."
    )


# ============================================================
# SAVE RESULT TO S3
# ============================================================

def save_result(query, code_used, result):
    """
    Guarda a análise no bucket de resultados.
    """

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

    logger.info(
        "Analysis result saved to s3://%s/%s",
        RESULTS_BUCKET,
        key,
    )

    return key


# ============================================================
# LAMBDA HANDLER
# ============================================================

def lambda_handler(event, context):

    logger.info(
        "Received event: %s",
        json.dumps(
            event,
            ensure_ascii=False,
        ),
    )

    query = event.get(
        "query",
        "Qual é o canal digital que regista o maior "
        "volume financeiro em transações fraudulentas?",
    )

    logger.info(
        "User query: %s",
        query,
    )

    session_id = None

    try:

        # ----------------------------------------------------
        # 1. Gerar código dinamicamente
        # ----------------------------------------------------

        logger.info(
            "Step 1: generating Python code."
        )

        python_code = generate_python_code(
            query
        )

        # ----------------------------------------------------
        # 2. Iniciar Code Interpreter
        # ----------------------------------------------------

        logger.info(
            "Step 2: starting Code Interpreter."
        )

        session_id = start_session()

        # ----------------------------------------------------
        # 3. Executar código
        # ----------------------------------------------------

        logger.info(
            "Step 3: executing generated code."
        )

        execution_result = execute_code(
            session_id,
            python_code,
        )

        logger.info(
            "Execution result: %s",
            execution_result,
        )

        # ----------------------------------------------------
        # 4. Guardar resultado
        # ----------------------------------------------------

        logger.info(
            "Step 4: saving result."
        )

        result_key = save_result(
            query,
            python_code,
            execution_result,
        )

        # ----------------------------------------------------
        # 5. Resposta
        # ----------------------------------------------------

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "query": query,
                    "generated_code": python_code,
                    "result": execution_result,
                    "result_s3": (
                        f"s3://{RESULTS_BUCKET}/{result_key}"
                    ),
                },
                ensure_ascii=False,
            ),
        }

    # ========================================================
    # QUOTA / RATE LIMIT
    # ========================================================

    except RuntimeError as exc:

        error_message = str(exc)

        logger.error(
            "Runtime error: %s",
            error_message,
        )

        if (
            "quota diária" in error_message.lower()
            or "quota" in error_message.lower()
            or "limitando" in error_message.lower()
        ):

            return {
                "statusCode": 429,
                "body": json.dumps(
                    {
                        "error": error_message,
                        "type": (
                            "BEDROCK_TOKEN_QUOTA_EXCEEDED"
                        ),
                    },
                    ensure_ascii=False,
                ),
            }

        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "error": error_message,
                    "type": "RUNTIME_ERROR",
                },
                ensure_ascii=False,
            ),
        }

    # ========================================================
    # AWS CLIENT ERROR
    # ========================================================

    except ClientError as exc:

        logger.exception(
            "AWS ClientError."
        )

        error = exc.response.get(
            "Error",
            {},
        )

        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "error": error.get(
                        "Message",
                        str(exc),
                    ),
                    "aws_error_code": error.get(
                        "Code",
                        "Unknown",
                    ),
                },
                ensure_ascii=False,
            ),
        }

    # ========================================================
    # GENERIC ERROR
    # ========================================================

    except Exception as exc:

        logger.exception(
            "Error executing data analysis."
        )

        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "error": str(exc),
                    "type": "INTERNAL_ERROR",
                },
                ensure_ascii=False,
            ),
        }

    # ========================================================
    # ALWAYS CLOSE SESSION
    # ========================================================

    finally:

        if session_id:

            try:

                stop_session(
                    session_id
                )

            except Exception:

                logger.exception(
                    "Failed to stop Code Interpreter session."
                )