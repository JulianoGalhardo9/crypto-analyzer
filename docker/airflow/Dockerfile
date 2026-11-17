# Imagem oficial do Airflow + o pacote crypto-analyzer (padrão "custom image" da documentação 3.4.0).
FROM apache/airflow:3.4.0-python3.12

# O pacote é instalado em modo editável em /opt/crypto-analyzer: o config.py acha os YAMLs
# subindo a partir do próprio arquivo, e no compose src/ e config/ são montados por cima,
# então uma mudança no código aparece no Airflow sem reconstruir a imagem.
COPY --chown=airflow:root pyproject.toml README.md /opt/crypto-analyzer/
COPY --chown=airflow:root src /opt/crypto-analyzer/src
COPY --chown=airflow:root config /opt/crypto-analyzer/config

# Fixar o apache-airflow e usar o arquivo de constraints impede que o pip troque a versão do
# Airflow ou de alguma dependência dele para satisfazer o nosso pacote.
RUN pip install --no-cache-dir "apache-airflow==${AIRFLOW_VERSION}" -e /opt/crypto-analyzer \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-3.12.txt"
