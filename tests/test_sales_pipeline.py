import os
import subprocess
import pandas as pd
from unittest import TestCase
from pandas._testing import assert_frame_equal
from airflow.providers.postgres.hooks.postgres import PostgresHook


AIRFLOW_HOME = os.environ.get('AIRFLOW_HOME')


def insert_initial_data(tablename, hook):
    """This script will populate database with initial data to run job"""
    conn_engine = hook.get_sqlalchemy_engine()
    sample_data = pd.read_csv(f'{AIRFLOW_HOME}/data/{tablename}.csv')
    sample_data.to_sql(name=tablename, con=conn_engine, if_exists='replace', index=False)


def create_table(tablename, hook):
    filename = tablename.replace('stg_', '')
    sql_stmt = open(f'/opt/airflow/sql/init/create_{filename}.sql').read()
    hook.run(sql_stmt.format(tablename=tablename))


def output_expected_as_df(filename):
    return pd.read_csv(f'{AIRFLOW_HOME}/data/expected/{filename}.csv')


def execute_dag(dag_id, execution_date):
    """Execute a DAG in a specific date this process wait for DAG run or fail to continue"""
    subprocess.run(["airflow", "dags", "backfill", "-s", execution_date, dag_id])


class TestDataTransfer(TestCase):

    def setUp(self):
        self.oltp_hook = PostgresHook('oltp')
        self.olap_hook = PostgresHook('olap')

    def test_validate_sales_pipeline(self):
        """Validate if Sales Pipeline DAG run correctly"""
        date = '2020-01-01'

        create_table('purchases', self.oltp_hook)
        insert_initial_data('purchases', self.oltp_hook)

        create_table('products', self.oltp_hook)
        insert_initial_data('products', self.oltp_hook)

        create_table('stg_purchases', self.olap_hook)
        create_table('stg_products', self.olap_hook)
        create_table('products_sales', self.olap_hook)

        execute_dag('products_sales_pipeline', date)

        stg_purchases_result = self.olap_hook.get_pandas_df('select * from stg_purchases')
        stg_purchases_expected = output_expected_as_df(f'stg_purchases_{date}')
        assert_frame_equal(stg_purchases_result, stg_purchases_expected)
        assert len(stg_purchases_result) == 3

        stg_products_result = self.olap_hook.get_pandas_df('select * from stg_products')
        stg_products_expected = output_expected_as_df('stg_products')
        assert_frame_equal(stg_products_result, stg_products_expected)
        assert len(stg_products_result) == 5

        product_sales_result = self.olap_hook.get_pandas_df('select * from products_sales')
        product_sales_expected = output_expected_as_df('products_sales')
        assert_frame_equal(product_sales_result, product_sales_expected)
        assert len(product_sales_result) == 3

        agg_result = self.olap_hook.get_pandas_df('select * from agg_sales_category')
        agg_expected = output_expected_as_df('agg_sales_category')
        assert_frame_equal(agg_result, agg_expected)
        assert len(agg_result) == 2
