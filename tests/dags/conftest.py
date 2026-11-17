import os
import tempfile

# Antes de qualquer import do Airflow: ele cria o AIRFLOW_HOME (padrão ~/airflow) ao ser
# importado. Os testes usam uma pasta temporária para não sujar a máquina.
os.environ["AIRFLOW_HOME"] = tempfile.mkdtemp(prefix="airflow-home-")
os.environ["AIRFLOW__CORE__LOAD_EXAMPLES"] = "False"
