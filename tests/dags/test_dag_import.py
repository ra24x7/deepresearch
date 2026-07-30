import pytest

airflow = pytest.importorskip("airflow", reason="Airflow requires Python <=3.12; run inside the container")

from airflow.models import DagBag


def test_dagbag_imports_without_errors():
    bag = DagBag(dag_folder="airflow/dags", include_examples=False)
    assert bag.import_errors == {}


def test_stack_healthcheck_tasks():
    bag = DagBag(dag_folder="airflow/dags", include_examples=False)
    dag = bag.get_dag("stack_healthcheck")
    assert dag is not None
    assert {t.task_id for t in dag.tasks} == {"check_opensearch", "check_postgres", "check_config"}
