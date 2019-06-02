import datetime

import boto3
import mock
import pytest
import requests

from botocore.exceptions import ClientError
from opentracing.ext import tags

from opentracing_instrumentation.client_hooks import boto3 as boto3_hooks


DYNAMODB_ENDPOINT_URL = 'http://localhost:8000'
DYNAMODB_CONFIG = {
    'endpoint_url': DYNAMODB_ENDPOINT_URL,
    'aws_access_key_id': '-',
    'aws_secret_access_key': '-',
    'region_name': 'us-east-1',
}


def create_users_table(dynamodb):
    dynamodb.create_table(
        TableName='users',
        KeySchema=[{
            'AttributeName': 'username',
            'KeyType': 'HASH'
        }],
        AttributeDefinitions=[{
            'AttributeName': 'username',
            'AttributeType': 'S'
        }],
        ProvisionedThroughput={
            'ReadCapacityUnits': 9,
            'WriteCapacityUnits': 9
        }
    )


@pytest.fixture
def dynamodb_mock():
    import moto
    with moto.mock_dynamodb2():
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        create_users_table(dynamodb)
        yield dynamodb


@pytest.fixture
def dynamodb():
    dynamodb = boto3.resource('dynamodb', **DYNAMODB_CONFIG)

    try:
        dynamodb.Table('users').delete()
    except ClientError as error:
        # you can not just use ResourceNotFoundException class
        # to catch an error since it doesn't exist until it's raised
        if error.__class__.__name__ != 'ResourceNotFoundException':
            raise

    create_users_table(dynamodb)

    # waiting until the table exists
    dynamodb.meta.client.get_waiter('table_exists').wait(TableName='users')

    return dynamodb


@pytest.fixture(autouse=True, scope='module')
def patch_boto3():
    boto3_hooks.install_patches()
    try:
        yield
    finally:
        boto3_hooks.reset_patches()


def assert_last_span(operation, tracer, response=None):
    span = tracer.recorder.get_spans()[-1]
    request_id = response and response['ResponseMetadata']['RequestId']
    assert span.operation_name == 'boto3:dynamodb:' + operation
    assert span.tags.get(tags.SPAN_KIND) == tags.SPAN_KIND_RPC_CLIENT
    assert span.tags.get(tags.COMPONENT) == 'boto3'
    assert span.tags.get('boto3.service_name') == 'dynamodb'
    assert span.tags.get('aws.request_id') == request_id


def _test(dynamodb, tracer):
    users = dynamodb.Table('users')

    response = users.put_item(Item={
        'username': 'janedoe',
        'first_name': 'Jane',
        'last_name': 'Doe',
    })
    assert_last_span('put_item', tracer, response)

    response = users.get_item(Key={'username': 'janedoe'})
    user = response['Item']
    assert user['first_name'] == 'Jane'
    assert user['last_name'] == 'Doe'
    assert_last_span('get_item', tracer, response)

    try:
        dynamodb.Table('test').delete_item(Key={'username': 'janedoe'})
    except ClientError as error:
        response = error.response
    assert_last_span('delete_item', tracer, response)

    response = users.creation_date_time
    assert isinstance(response, datetime.datetime)
    assert_last_span('describe_table', tracer)


def is_dynamodb_running():
    try:
        # feel free to suggest better solution for this check
        response = requests.get(DYNAMODB_ENDPOINT_URL, timeout=1)
        return response.status_code == 400
    except requests.exceptions.ConnectionError:
        return False


def is_moto_presented():
    try:
        import moto
        return True
    except ImportError:
        return False


@pytest.mark.skipif(not is_dynamodb_running(),
                    reason='DynamoDB is not running or cannot connect')
def test_boto3(dynamodb, tracer):
    _test(dynamodb, tracer)


@pytest.mark.skipif(not is_moto_presented(),
                    reason='moto module is not presented')
def test_boto3_with_moto(dynamodb_mock, tracer):
    _test(dynamodb_mock, tracer)


@mock.patch.object(boto3_hooks, 'patcher')
def test_set_custom_patcher(default_patcher):
    patcher = mock.Mock()
    boto3_hooks.set_patcher(patcher)

    assert boto3_hooks.patcher is not default_patcher
    assert boto3_hooks.patcher is patcher

    boto3_hooks.install_patches()
    boto3_hooks.reset_patches()

    patcher.install_patches.assert_called_once()
    patcher.reset_patches.assert_called_once()
