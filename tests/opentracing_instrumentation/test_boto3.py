import datetime
import io

import boto3
import mock
import pytest
import requests
import testfixtures

from botocore.exceptions import ClientError
from opentracing.ext import tags

from opentracing_instrumentation.client_hooks import boto3 as boto3_hooks


DYNAMODB_ENDPOINT_URL = 'http://localhost:4569'
S3_ENDPOINT_URL = 'http://localhost:4572'

DYNAMODB_CONFIG = {
    'endpoint_url': DYNAMODB_ENDPOINT_URL,
    'aws_access_key_id': '-',
    'aws_secret_access_key': '-',
    'region_name': 'us-east-1',
}
S3_CONFIG = dict(DYNAMODB_CONFIG, endpoint_url=S3_ENDPOINT_URL)


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


@pytest.fixture
def s3_mock():
    import moto
    with moto.mock_s3():
        s3 = boto3.client('s3', region_name='us-east-1')
        yield s3


@pytest.fixture
def s3():
    return boto3.client('s3', **S3_CONFIG)


@pytest.fixture(autouse=True)
def patch_boto3():
    boto3_hooks.install_patches()
    try:
        yield
    finally:
        boto3_hooks.reset_patches()


def assert_last_span(kind, service_name, operation, tracer, response=None):
    span = tracer.recorder.get_spans()[-1]
    request_id = response and response['ResponseMetadata'].get('RequestId')
    assert span.operation_name == 'boto3:{}:{}:{}'.format(
        kind, service_name, operation
    )
    assert span.tags.get(tags.SPAN_KIND) == tags.SPAN_KIND_RPC_CLIENT
    assert span.tags.get(tags.COMPONENT) == 'boto3'
    assert span.tags.get('boto3.service_name') == service_name
    if request_id:
        assert span.tags.get('aws.request_id') == request_id


def _test_dynamodb(dynamodb, tracer):
    users = dynamodb.Table('users')

    response = users.put_item(Item={
        'username': 'janedoe',
        'first_name': 'Jane',
        'last_name': 'Doe',
    })
    assert_last_span('resource', 'dynamodb', 'put_item', tracer, response)

    response = users.get_item(Key={'username': 'janedoe'})
    user = response['Item']
    assert user['first_name'] == 'Jane'
    assert user['last_name'] == 'Doe'
    assert_last_span('resource', 'dynamodb', 'get_item', tracer, response)

    try:
        dynamodb.Table('test').delete_item(Key={'username': 'janedoe'})
    except ClientError as error:
        response = error.response
    assert_last_span('resource', 'dynamodb', 'delete_item', tracer, response)

    response = users.creation_date_time
    assert isinstance(response, datetime.datetime)
    assert_last_span('resource', 'dynamodb', 'describe_table', tracer)


def _test_s3(s3, tracer):
    fileobj = io.BytesIO(b'test data')
    bucket = 'test-bucket'

    response = s3.create_bucket(Bucket=bucket)
    assert_last_span('client', 's3', 'create_bucket', tracer, response)

    response = s3.upload_fileobj(fileobj, bucket, 'test.txt')
    assert_last_span('client', 's3', 'upload_fileobj', tracer, response)


def is_service_running(endpoint_url, expected_status_code):
    try:
        # feel free to suggest better solution for this check
        response = requests.get(endpoint_url, timeout=1)
        return response.status_code == expected_status_code
    except requests.exceptions.ConnectionError:
        return False


def is_dynamodb_running():
    return is_service_running(DYNAMODB_ENDPOINT_URL, 502)


def is_s3_running():
    return is_service_running(S3_ENDPOINT_URL, 200)


def is_moto_presented():
    try:
        import moto
        return True
    except ImportError:
        return False


@pytest.mark.skipif(not is_dynamodb_running(),
                    reason='DynamoDB is not running or cannot connect')
def test_boto3_dynamodb(thread_safe_tracer, dynamodb):
    _test_dynamodb(dynamodb, thread_safe_tracer)


@pytest.mark.skipif(not is_moto_presented(),
                    reason='moto module is not presented')
def test_boto3_dynamodb_with_moto(thread_safe_tracer, dynamodb_mock):
    _test_dynamodb(dynamodb_mock, thread_safe_tracer)


@pytest.mark.skipif(not is_s3_running(),
                    reason='S3 is not running or cannot connect')
def test_boto3_s3(s3, thread_safe_tracer):
    _test_s3(s3, thread_safe_tracer)


@pytest.mark.skipif(not is_moto_presented(),
                    reason='moto module is not presented')
def test_boto3_s3_with_moto(s3_mock, thread_safe_tracer):
    _test_s3(s3_mock, thread_safe_tracer)


@testfixtures.log_capture()
def test_boto3_s3_missing_func_instrumentation(capture):
    class Patcher(boto3_hooks.Boto3Patcher):
        S3_FUNCTIONS_TO_INSTRUMENT = 'missing_func',

    Patcher().install_patches()
    capture.check(('root', 'WARNING', 'S3 function missing_func not found'))


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
